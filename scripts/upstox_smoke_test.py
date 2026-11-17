"""Upstox API v3 Smoke Test Suite (Section 17.9).

Executes live connectivity verification across:
1. Equity Quote (RELIANCE.NS)
2. Daily Candle series
3. India VIX Quote (^INDIAVIX)
4. NSE Market Operational Status
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file explicitly
load_dotenv()

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.data.upstox import UpstoxClient



def run_smoke_test():
    print("=" * 65)
    print("AURA-NSE Pro — Upstox API v3 Data Layer Smoke Test")
    print("=" * 65)

    token = os.getenv("UPSTOX_ACCESS_TOKEN") or os.getenv("UPSTOX_ANALYTICS_TOKEN")
    if not token:
        print("[STATUS: BLOCKED (TOKEN_PENDING)]")
        print("[INFO] UPSTOX_ACCESS_TOKEN / UPSTOX_ANALYTICS_TOKEN not set in environment or vault.")
        print("       To enable Tier-2 Upstox verification:")
        print("       1. Log into Upstox Developer Portal (account.upstox.com/developer/apps)")
        print("       2. Generate your API Key, Secret, and Access Token")
        print("       3. Add UPSTOX_ACCESS_TOKEN to GitHub Secrets and local .env\n")
        print("Testing Client Fallback & Contract Verification...")
    else:
        masked_token = f"{token[:4]}...{token[-4:]}" if len(token) > 8 else "***"
        print(f"[AUTH] Upstox Access Token Loaded: {masked_token}")

    client = UpstoxClient(token=token)

    # 1. Test Market Status Endpoint
    print("\n[1/4] Testing Market Status Endpoint...")
    status_res = client.get_market_status()
    print(f"      Result: {status_res.get('status')} | Operational: {status_res.get('operational_status', 'N/A')}")

    # 2. Test Equity Quote (RELIANCE)
    print("\n[2/4] Testing Equity Quote (RELIANCE.NS)...")
    quote_res = client.get_market_quote("RELIANCE.NS")
    if "error" in quote_res:
        print(f"      Quote Response: {quote_res.get('error')}")
    else:
        print(f"      LTP: ₹{quote_res.get('ltp')} | Vol: {quote_res.get('volume'):,} | Lag: {quote_res.get('data_lag_seconds')}s")

    # 3. Test India VIX Quote
    print("\n[3/4] Testing India VIX Quote (^INDIAVIX)...")
    vix_res = client.get_market_quote("^INDIAVIX")
    if "error" in vix_res:
        print(f"      India VIX Response: {vix_res.get('error')}")
    else:
        print(f"      VIX LTP: {vix_res.get('ltp')} | Lag: {vix_res.get('data_lag_seconds')}s")

    # 4. Test Historical Daily Candles
    print("\n[4/4] Testing Historical Candles (RELIANCE.NS)...")
    candles = client.get_historical_candles("RELIANCE.NS", interval="day", force_upstox=True)
    print(f"      Candles Retrieved: {len(candles)} bars")

    # Expiry Check
    days_left = client.get_token_days_remaining()
    print(f"\n[VAULT] Analytics Token Days Remaining: {days_left} days")
    print("=" * 65)
    print("Smoke Test Execution Complete.")



if __name__ == "__main__":
    run_smoke_test()
