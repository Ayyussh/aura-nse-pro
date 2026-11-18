"""AURA-NSE Pro Telegram Connectivity & Ping Diagnostics.

Usage:
    python scripts/test_telegram.py
    python scripts/test_telegram.py --token <BOT_TOKEN> --chat-id <CHAT_ID>
"""

import argparse
import os
import sys
import httpx

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.config import settings
from backend.data.holiday_calendar import get_ist_now


def main():
    parser = argparse.ArgumentParser(description="Test Telegram Alert Dispatch")
    parser.add_argument("--token", help="Telegram Bot Token (optional override)", default="")
    parser.add_argument("--chat-id", help="Telegram Chat ID (optional override)", default="")
    args = parser.parse_args()

    token = args.token or os.environ.get("TELEGRAM_BOT_TOKEN") or getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat_id = args.chat_id or os.environ.get("TELEGRAM_CHAT_ID") or getattr(settings, "TELEGRAM_CHAT_ID", "")

    from backend.core.telegram_subscribers import sync_subscribers, load_subscribers_data
    sub_data = load_subscribers_data()
    all_subscribers = sync_subscribers(token if token else None)

    print("\n--- AURA-NSE Pro Telegram Diagnostic Check ---")
    print(f"Token configured: {'YES (masked: ' + token[:6] + '...' + token[-4:] + ')' if token else 'NO (Missing)'}")
    print(f"Registered Devices / Subscribers ({len(all_subscribers)}): {', '.join(all_subscribers) if all_subscribers else 'None'}")

    if not token:
        print("\n❌ ERROR: TELEGRAM_BOT_TOKEN not found.")
        print("Please configure TELEGRAM_BOT_TOKEN in .env or via --token.")
        sys.exit(1)

    if not all_subscribers and not chat_id:
        print("\n❌ ERROR: No Telegram subscribers found.")
        print("Open the bot on any Telegram device and tap /start, or set TELEGRAM_CHAT_ID in .env")
        sys.exit(1)

    from backend.core.pipeline import send_telegram_alert
    now_ist = get_ist_now().strftime("%Y-%m-%d %I:%M:%S %p IST")
    test_message = (
        f"🤖 *AURA-NSE Pro — Telegram Alert Test*\n\n"
        f"✅ Broadcast verified successfully!\n"
        f"📱 *Active Subscribers:* {len(all_subscribers)}\n"
        f"🕒 *Timestamp:* `{now_ist}`\n\n"
        f"_Educational decision support, not investment advice._"
    )

    print(f"\nBroadcasting test ping to all {len(all_subscribers)} registered devices...")
    success = send_telegram_alert(test_message)
    if success:
        print("🎉 SUCCESS: Alert delivered to registered devices! Check your Telegram app.")
        sys.exit(0)
    else:
        print("❌ Alert delivery failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
