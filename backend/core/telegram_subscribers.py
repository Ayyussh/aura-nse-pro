"""AURA-NSE Pro Dynamic Telegram Subscriber Manager.

Enables any device or account that adds/starts the bot to automatically
receive all automated market alerts without manual configuration.

Features:
- Auto-discovery via Telegram `getUpdates` API.
- Supports individual users (/start), Telegram Channels, and Groups.
- Automatic welcome message on first device registration.
- Persistent subscriber registry in `data/telegram_subscribers.json`.
- Automatic cleanup of blocked or deactivated chat IDs (HTTP 403).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import httpx

from backend.core.config import PROJECT_ROOT, settings
from backend.data.holiday_calendar import get_ist_now

logger = logging.getLogger("aura.telegram_subscribers")

SUBSCRIBERS_FILE = PROJECT_ROOT / "data" / "telegram_subscribers.json"


def load_subscribers_data() -> dict[str, Any]:
    """Load subscriber registry from disk, initializing if missing."""
    if SUBSCRIBERS_FILE.exists():
        try:
            with open(SUBSCRIBERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "subscribers" in data:
                    return data
        except Exception as e:
            logger.warning(f"Error reading {SUBSCRIBERS_FILE}: {e}. Reinitializing.")

    # Default structure
    initial_data: dict[str, Any] = {
        "updated_at_ist": get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST"),
        "last_update_id": 0,
        "subscribers": {},
    }

    # Seed with static TELEGRAM_CHAT_ID from settings if present
    raw_env_ids = settings.TELEGRAM_CHAT_ID
    if raw_env_ids:
        for cid in str(raw_env_ids).replace(";", ",").split(","):
            cid_clean = cid.strip()
            if cid_clean:
                initial_data["subscribers"][cid_clean] = {
                    "source": "ENV_SEED",
                    "added_at_ist": get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST"),
                    "type": "unknown",
                }

    return initial_data


def save_subscribers_data(data: dict[str, Any]) -> None:
    """Save subscriber registry to disk."""
    try:
        SUBSCRIBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data["updated_at_ist"] = get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST")
        with open(SUBSCRIBERS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save subscribers to {SUBSCRIBERS_FILE}: {e}")


def send_welcome_message(token: str, chat_id: str, title: str = "") -> None:
    """Send one-time onboarding confirmation when a new device starts the bot."""
    welcome_text = (
        f"⚡ *AURA Trading System — Device Connected!*\n\n"
        f"This device is now registered to receive all live automated market alerts:\n"
        f"• *08:55 / 09:00 AM IST:* Pre-Market Screening & High-Conviction Trades\n"
        f"• *09:15 AM IST:* Market Open Gap & Execution Verification\n"
        f"• *13:00 PM IST:* Mid-Day Intraday Risk & Trailing Stop Audits\n"
        f"• *15:45 PM IST:* Post-Market Trade Grading & P&L Attribution\n\n"
        f"🔔 _No further setup required. You will receive alerts here automatically._"
    )
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": welcome_text,
        "parse_mode": "Markdown",
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            client.post(url, json=payload)
            logger.info(f"Sent welcome onboarding message to new device {chat_id}")
    except Exception as e:
        logger.warning(f"Could not deliver welcome message to {chat_id}: {e}")


def sync_subscribers(token: str | None = None) -> list[str]:
    """Poll Telegram getUpdates to automatically discover and register any new devices.

    Returns the complete deduplicated list of active subscriber chat IDs.
    """
    bot_token = token or settings.TELEGRAM_BOT_TOKEN
    data = load_subscribers_data()
    subscribers: dict[str, Any] = data.setdefault("subscribers", {})

    # Ensure any env IDs are always present
    raw_env_ids = settings.TELEGRAM_CHAT_ID
    if raw_env_ids:
        for cid in str(raw_env_ids).replace(";", ",").split(","):
            cid_clean = cid.strip()
            if cid_clean and cid_clean not in subscribers:
                subscribers[cid_clean] = {
                    "source": "ENV_SEED",
                    "added_at_ist": get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST"),
                    "type": "unknown",
                }

    if not bot_token:
        save_subscribers_data(data)
        return list(subscribers.keys())

    last_update_id = data.get("last_update_id", 0)
    params: dict[str, Any] = {"timeout": 2}
    if last_update_id > 0:
        params["offset"] = last_update_id + 1

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"https://api.telegram.org/bot{bot_token}/getUpdates", params=params)
            if resp.status_code == 200:
                result = resp.json().get("result", [])
                max_update_id = last_update_id

                for update in result:
                    up_id = update.get("update_id", 0)
                    if up_id > max_update_id:
                        max_update_id = up_id

                    # 1. Message from user, group, or channel
                    msg = (
                        update.get("message")
                        or update.get("edited_message")
                        or update.get("channel_post")
                        or update.get("edited_channel_post")
                        or update.get("my_chat_member")
                    )
                    if not msg:
                        continue

                    chat = msg.get("chat", {})
                    chat_id = str(chat.get("id", "")).strip()
                    if not chat_id:
                        continue

                    chat_type = chat.get("type", "unknown")
                    sender = msg.get("from", {})
                    username = sender.get("username") or chat.get("username") or chat.get("title") or ""
                    first_name = sender.get("first_name") or chat.get("title") or "User"
                    text = (msg.get("text") or "").strip().lower()

                    # Handle explicit unsubscribe
                    if text in ("/stop", "/unsubscribe", "unsubscribe"):
                        if chat_id in subscribers:
                            logger.info(f"Device {chat_id} ({first_name}) requested unsubscribe.")
                            del subscribers[chat_id]
                        continue

                    # Register subscriber
                    is_new = chat_id not in subscribers
                    subscribers[chat_id] = {
                        "username": username,
                        "first_name": first_name,
                        "type": chat_type,
                        "source": "AUTO_DISCOVERED",
                        "last_seen_ist": get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST"),
                    }
                    if is_new:
                        subscribers[chat_id]["added_at_ist"] = get_ist_now().strftime("%Y-%m-%d %H:%M:%S IST")
                        logger.info(f"Registered new Telegram device/subscriber: {chat_id} ({first_name})")
                        # Greet new subscriber
                        send_welcome_message(bot_token, chat_id, first_name)

                data["last_update_id"] = max_update_id
                save_subscribers_data(data)
            else:
                logger.warning(f"Telegram getUpdates returned HTTP {resp.status_code}: {resp.text}")
    except Exception as e:
        logger.warning(f"Could not poll Telegram updates for auto-discovery: {e}")

    # Return valid chat IDs
    return list(subscribers.keys())


def remove_subscriber(chat_id: str) -> None:
    """Remove an inactive or blocked chat ID from the registry."""
    data = load_subscribers_data()
    subscribers: dict[str, Any] = data.setdefault("subscribers", {})
    if chat_id in subscribers:
        logger.info(f"Removing inactive/blocked subscriber {chat_id}")
        del subscribers[chat_id]
        save_subscribers_data(data)
