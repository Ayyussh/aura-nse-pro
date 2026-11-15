"""Unit and Integration Tests for Upstox Multi-Tier Rate Limiter & Data Routing.

Validates:
1. Multi-tier limits: 50 req/sec, 500 req/min, 2,000 req/30min.
2. Shared limiter instance across multiple UpstoxClient instances and threads.
3. Exponential backoff and Retry-After handling on HTTP 429 (Too Many Requests).
4. Data Routing: Bulk history (> 15 days) sourced from NSE Bhavcopy / Historical Store,
   while recent / intraday data is routed to Upstox.
"""

import collections
import datetime
import threading
import time
from unittest.mock import patch, MagicMock
import pytest
import httpx
import pandas as pd

from backend.data.upstox import (
    SharedMultiTierRateLimiter,
    shared_upstox_limiter,
    UpstoxClient,
)
from backend.data.historical_store import HistoricalDataStore


@pytest.fixture(autouse=True)
def reset_limiter():
    """Reset the shared limiter state before and after each test."""
    shared_upstox_limiter.reset_for_testing()
    yield
    shared_upstox_limiter.reset_for_testing()


def test_limiter_tier_definitions():
    """Verify that limiter defines 50 req/s, 500 req/min, and 2000 req/30m."""
    limiter = SharedMultiTierRateLimiter()
    tiers = limiter.tiers
    assert len(tiers) == 3
    # Tier 1: 50 in 1 second
    assert tiers[0][0] == 50
    assert tiers[0][1] == 1.0
    # Tier 2: 500 in 60 seconds
    assert tiers[1][0] == 500
    assert tiers[1][1] == 60.0
    # Tier 3: 2000 in 1800 seconds
    assert tiers[2][0] == 2000
    assert tiers[2][1] == 1800.0


def test_shared_limiter_singleton_across_clients():
    """Verify that multiple UpstoxClient instances share the exact same rate limiter."""
    client_a = UpstoxClient(token="test_token_a")
    client_b = UpstoxClient(token="test_token_b")
    assert client_a.rate_limiter is client_b.rate_limiter
    assert client_a.rate_limiter is shared_upstox_limiter


def test_50_req_per_second_capacity():
    """Verify that 50 requests are permitted immediately, and 51st request waits for 1s window."""
    limiter = SharedMultiTierRateLimiter()
    now = time.time()
    # Inject 50 timestamps within the last 0.5s
    with limiter._lock:
        for i in range(50):
            limiter._timestamps.append(now - 0.5 + (i * 0.005))

    stats = limiter.get_stats()
    assert stats["tier_metrics"]["1-sec (50 req/s)"]["count"] == 50
    assert stats["tier_metrics"]["1-sec (50 req/s)"]["remaining"] == 0

    # Acquire should wait until the oldest timestamp reaches 1.0s age
    t0 = time.time()
    limiter.acquire()
    elapsed = time.time() - t0
    # Expected sleep is around 0.5s
    assert elapsed >= 0.40, f"Expected acquire to wait for ~0.5s, waited {elapsed:.3f}s"


def test_500_req_per_minute_capacity():
    """Verify that 500 requests per minute ceiling is strictly respected."""
    limiter = SharedMultiTierRateLimiter()
    now = time.time()
    # Inject 500 timestamps spaced over the last 30 seconds
    with limiter._lock:
        for i in range(500):
            limiter._timestamps.append(now - 30.0 + (i * 0.05))

    stats = limiter.get_stats()
    assert stats["tier_metrics"]["1-min (500 req/min)"]["count"] == 500
    assert stats["tier_metrics"]["1-min (500 req/min)"]["remaining"] == 0


def test_2000_req_per_30min_capacity():
    """Verify that 2,000 requests per 30 minutes ceiling is strictly respected."""
    limiter = SharedMultiTierRateLimiter()
    now = time.time()
    # Inject 2,000 timestamps spaced over the last 15 minutes (900s)
    with limiter._lock:
        for i in range(2000):
            limiter._timestamps.append(now - 900.0 + (i * 0.4))

    stats = limiter.get_stats()
    assert stats["tier_metrics"]["30-min (2000 req/30m)"]["count"] == 2000
    assert stats["tier_metrics"]["30-min (2000 req/30m)"]["remaining"] == 0


def test_429_backoff_and_retry_after():
    """Verify that HTTP 429 triggers backoff and respects Retry-After header."""
    limiter = SharedMultiTierRateLimiter()

    # 1. Backoff with explicit Retry-After
    limiter.notify_429(retry_after_sec=0.25)
    stats = limiter.get_stats()
    assert stats["active_backoff_seconds"] > 0.0
    assert stats["consecutive_429_count"] == 1

    t0 = time.time()
    limiter.acquire()
    elapsed = time.time() - t0
    assert elapsed >= 0.20, f"Expected backoff wait of >=0.20s, got {elapsed:.3f}s"

    # 2. Success resets consecutive 429 count
    limiter.notify_success()
    stats_after = limiter.get_stats()
    assert stats_after["consecutive_429_count"] == 0


def test_thread_safe_concurrent_acquires():
    """Verify that concurrent threads acquire safely without race conditions."""
    limiter = SharedMultiTierRateLimiter()
    acquired_count = 0
    lock = threading.Lock()

    def worker():
        nonlocal acquired_count
        for _ in range(5):
            limiter.acquire()
            with lock:
                acquired_count += 1

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert acquired_count == 20
    assert len(limiter._timestamps) == 20


def test_data_routing_bulk_history_uses_nse_files():
    """Verify that requests for > 15 days of daily bars route to official NSE Bhavcopy / HistoricalStore."""
    client = UpstoxClient(token="dummy_token")

    # Seed test parquet bar in HistoricalDataStore
    store = HistoricalDataStore()
    dates = pd.date_range("2026-08-01", periods=20, freq="B")
    test_df = pd.DataFrame({
        "open": [100.0] * 20,
        "high": [105.0] * 20,
        "low": [98.0] * 20,
        "close": [102.0] * 20,
        "volume": [50000] * 20,
    }, index=dates)
    store.store_ohlcv("ROUTETEST.NS", test_df)

    # Request 25 days of daily bars: must route to NSE Bhavcopy Store, not Upstox API
    with patch.object(client, "_request_with_retry") as mock_http:
        candles = client.get_historical_candles(
            symbol="ROUTETEST.NS",
            interval="day",
            from_date="2026-08-01",
            to_date="2026-08-25",
        )
        # Upstox HTTP API must NOT have been called
        assert mock_http.call_count == 0
        assert len(candles) > 0
        assert candles[0]["source"] == "NSE_BHAVCOPY_STORE"


def test_data_routing_recent_and_intraday_uses_upstox():
    """Verify that recent data (<= 15 days) and intraday (1m/5m) candles route to Upstox API."""
    client = UpstoxClient(token="dummy_token")

    # Mock Upstox HTTP response for 5-minute intraday candle
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "candles": [
                ["2026-11-13T09:15:00+05:30", 2500.0, 2520.0, 2495.0, 2510.0, 15000, 0],
                ["2026-11-13T09:20:00+05:30", 2510.0, 2530.0, 2505.0, 2525.0, 22000, 0],
            ]
        }
    }

    with patch.object(client, "_request_with_retry", return_value=mock_resp) as mock_http:
        candles = client.get_historical_candles(
            symbol="RELIANCE.NS",
            interval="5minute",
            from_date="2026-11-13",
            to_date="2026-11-13",
        )
        assert mock_http.call_count == 1
        assert len(candles) == 2
        assert candles[0]["source"] == "UPSTOX_V3"
        assert candles[0]["close"] == 2510.0
