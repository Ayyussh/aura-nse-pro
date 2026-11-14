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

    print("\n--- AURA-NSE Pro Telegram Diagnostic Check ---")
    print(f"Token configured: {'YES (masked: ' + token[:6] + '...' + token[-4:] + ')' if token else 'NO (Missing)'}")
    print(f"Chat ID configured: {'YES (' + str(chat_id) + ')' if chat_id else 'NO (Missing)'}")

    if not token or not chat_id:
        print("\n❌ ERROR: Telegram credentials not found.")
        print("Please configure them via one of these two methods:")
        print("1. In your local .env file:")
        print("   TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRstuVWXyz")
        print("   TELEGRAM_CHAT_ID=123456789")
        print("\n2. Pass them directly to this script:")
        print("   python scripts/test_telegram.py --token <BOT_TOKEN> --chat-id <CHAT_ID>")
        print("\n3. OR run manually via GitHub Actions (where your GitHub Secrets are already set).")
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    now_ist = get_ist_now().strftime("%Y-%m-%d %I:%M:%S %p IST")
    test_message = (
        f"🤖 *AURA-NSE Pro — Telegram Alert Test*\n\n"
        f"✅ Connection verified successfully!\n"
        f"🕒 *Timestamp:* `{now_ist}`\n\n"
        f"_Educational decision support, not investment advice._"
    )

    payload = {
        "chat_id": chat_id,
        "text": test_message,
        "parse_mode": "Markdown",
    }

    print(f"\nSending test ping to Telegram API for chat {chat_id}...")
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                print("🎉 SUCCESS: Alert delivered! Check your Telegram app.")
                sys.exit(0)
            else:
                print(f"❌ Telegram API returned error HTTP {resp.status_code}:")
                print(resp.text)
                sys.exit(1)
    except Exception as e:
        print(f"❌ Connection error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
