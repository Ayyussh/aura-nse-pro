"""Tests for AURA Dynamic Telegram Subscriber Discovery & Alert Broadcast."""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.core import telegram_subscribers
from backend.core.pipeline import send_telegram_alert


def test_load_save_subscribers(tmp_path, monkeypatch):
    test_file = tmp_path / "telegram_subscribers.json"
    monkeypatch.setattr(telegram_subscribers, "SUBSCRIBERS_FILE", test_file)

    data = telegram_subscribers.load_subscribers_data()
    assert "subscribers" in data
    assert isinstance(data["subscribers"], dict)

    data["subscribers"]["999999"] = {"source": "TEST", "first_name": "TestUser"}
    telegram_subscribers.save_subscribers_data(data)

    reloaded = telegram_subscribers.load_subscribers_data()
    assert "999999" in reloaded["subscribers"]
    assert reloaded["subscribers"]["999999"]["first_name"] == "TestUser"


def test_sync_subscribers_auto_discovery(tmp_path, monkeypatch):
    test_file = tmp_path / "telegram_subscribers.json"
    monkeypatch.setattr(telegram_subscribers, "SUBSCRIBERS_FILE", test_file)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 100,
                "message": {
                    "chat": {"id": 111222, "type": "private"},
                    "from": {"first_name": "Alice", "username": "alice"},
                    "text": "/start",
                },
            },
            {
                "update_id": 101,
                "message": {
                    "chat": {"id": 333444, "type": "private"},
                    "from": {"first_name": "Bob"},
                    "text": "Hello bot",
                },
            },
        ],
    }

    with patch("httpx.Client.get", return_value=mock_resp), patch("httpx.Client.post"):
        subs = telegram_subscribers.sync_subscribers(token="fake_token")
        assert "111222" in subs
        assert "333444" in subs

    # Check unsubscription
    mock_resp_unsub = MagicMock()
    mock_resp_unsub.status_code = 200
    mock_resp_unsub.json.return_value = {
        "ok": True,
        "result": [
            {
                "update_id": 102,
                "message": {
                    "chat": {"id": 111222, "type": "private"},
                    "from": {"first_name": "Alice"},
                    "text": "/stop",
                },
            }
        ],
    }

    with patch("httpx.Client.get", return_value=mock_resp_unsub):
        subs_after = telegram_subscribers.sync_subscribers(token="fake_token")
        assert "111222" not in subs_after
        assert "333444" in subs_after


def test_remove_subscriber(tmp_path, monkeypatch):
    test_file = tmp_path / "telegram_subscribers.json"
    monkeypatch.setattr(telegram_subscribers, "SUBSCRIBERS_FILE", test_file)

    data = {
        "updated_at_ist": "2026-11-18 10:00:00 IST",
        "last_update_id": 50,
        "subscribers": {"55555": {"first_name": "Charlie"}},
    }
    with open(test_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    telegram_subscribers.remove_subscriber("55555")
    reloaded = telegram_subscribers.load_subscribers_data()
    assert "55555" not in reloaded["subscribers"]


def test_send_telegram_alert_broadcast(monkeypatch):
    monkeypatch.setattr("backend.core.config.settings.TELEGRAM_BOT_TOKEN", "mock_token")
    monkeypatch.setattr(
        "backend.core.telegram_subscribers.sync_subscribers",
        lambda token: ["1001", "1002"],
    )

    sent_to = []

    def mock_post(url, json=None, **kwargs):
        resp = MagicMock()
        resp.status_code = 200
        sent_to.append(json["chat_id"])
        return resp

    with patch("httpx.Client.post", side_effect=mock_post):
        success = send_telegram_alert("Test message")
        assert success is True
        assert "1001" in sent_to
        assert "1002" in sent_to
