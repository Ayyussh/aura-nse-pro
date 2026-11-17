"""Section 20.0 Item 6: Decode Upstox Analytics Token Expiry & Show Day Count Computation."""

import base64
import datetime
import json
from pathlib import Path

def decode_token():
    env_file = Path(".env")
    token = ""
    if env_file.exists():
        for line in open(env_file, encoding="utf-8"):
            line = line.strip()
            if line.startswith("UPSTOX_ANALYTICS_TOKEN="):
                token = line.split("=", 1)[1].strip("\"' ")

    if not token:
        print("ERROR: UPSTOX_ANALYTICS_TOKEN not found in .env")
        return

    parts = token.split(".")
    if len(parts) < 2:
        print("ERROR: Invalid JWT format")
        return

    def decode_b64(seg: str) -> dict:
        seg += "=" * ((4 - len(seg) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(seg.encode("utf-8")))

    header = decode_b64(parts[0])
    payload = decode_b64(parts[1])

    print("=" * 60)
    print("UPSTOX ANALYTICS ACCESS TOKEN AUDIT")
    print("=" * 60)
    print("Header:")
    print(json.dumps(header, indent=2))
    print("\nPayload (Sanitized):")
    sanitized_payload = {k: v for k, v in payload.items() if k not in ("client_secret", "refresh_token")}
    print(json.dumps(sanitized_payload, indent=2))

    exp = payload.get("exp")
    iat = payload.get("iat")

    print("\nToken Claims Breakdown:")
    print(f"  Algorithm (alg)        : {header.get('alg')}")
    print(f"  Token Type (typ)       : {header.get('typ')}")
    print(f"  User ID                : {payload.get('user_id')}")
    print(f"  Issued At (iat epoch)  : {iat}")
    print(f"  Expires At (exp epoch) : {exp}")

    if exp:
        exp_utc = datetime.datetime.fromtimestamp(exp, datetime.timezone.utc)
        ist_offset = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
        exp_ist = exp_utc.astimezone(ist_offset)
        now_utc = datetime.datetime.now(datetime.timezone.utc)
        now_ist = now_utc.astimezone(ist_offset)

        diff_seconds = exp - now_utc.timestamp()
        days_remaining = diff_seconds / 86400.0

        print(f"\nExact Timestamps:")
        print(f"  Current Time (UTC)     : {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Current Time (IST)     : {now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
        print(f"  Expiry Time (UTC)      : {exp_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Expiry Time (IST)      : {exp_ist.strftime('%Y-%m-%d %H:%M:%S IST')}")
        
        print(f"\nDay Count Mathematical Computation:")
        print(f"  Formula: Days = (exp_epoch - now_epoch) / 86,400 seconds/day")
        print(f"  Calculation: ({exp} - {now_utc.timestamp():.0f}) / 86,400")
        print(f"             = {diff_seconds:.2f} seconds / 86,400")
        print(f"             = {days_remaining:.2f} days")
        print(f"  Status: {'VALID & ACTIVE' if days_remaining > 0 else 'EXPIRED'}")
    print("=" * 60)

if __name__ == "__main__":
    decode_token()
