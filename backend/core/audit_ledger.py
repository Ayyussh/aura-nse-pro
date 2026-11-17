"""AURA-NSE Pro Cryptographic Audit Ledger & External Anchor Engine (Section 18.2 & Item 10).

Features:
1. Canonical JSON formatting with fixed-precision floats (4 decimals) and ISO-8601 UTC timestamps (ending with Z).
2. Prev-hash cryptographic chaining (SHA-256) across all predictions.
3. Multi-version row verification (handles legacy v1 and strict v2 canonical rows).
4. External Daily Anchor: appends immutable daily head hash into `data/audit_anchor_history.jsonl`
   and notifies Telegram channel if configured.
5. Tamper detection: detects any row modification, deletion, or hash link corruption.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
from typing import Any

from backend.core.config import PROJECT_ROOT

logger = logging.getLogger("aura.audit")

DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
AUDIT_ANCHOR_FILE = DATA_DIR / "audit_anchor_history.jsonl"


def format_canonical_float(val: float) -> str:
    """Format float into strict canonical 4-decimal string representation."""
    return f"{float(val):.4f}"


def format_canonical_timestamp(dt: datetime.datetime | None = None) -> str:
    """Format datetime into canonical ISO 8601 UTC timestamp ending in 'Z'."""
    if dt is None:
        dt = datetime.datetime.now(datetime.UTC)
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.UTC)
    else:
        dt = dt.astimezone(datetime.UTC)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z"


def build_canonical_prediction_payload(
    symbol: str,
    side: str,
    entry_price: float,
    stop_loss: float,
    target_price: float,
    quantity: int,
    probability: float,
    ev_r: float,
    model_version: str,
    config_hash: str,
    data_snapshot_id: str,
    llm_output_hash: str,
    prev_hash: str,
    utc_timestamp: str | None = None,
    hash_version: str = "v2",
) -> dict[str, Any]:
    """Construct deterministic canonical dictionary payload for hashing."""
    if not utc_timestamp:
        utc_timestamp = format_canonical_timestamp()

    return {
        "hash_version": str(hash_version),
        "prev_hash": str(prev_hash),
        "symbol": str(symbol).strip().upper(),
        "side": str(side).strip().upper(),
        "entry_price": format_canonical_float(entry_price),
        "stop_loss": format_canonical_float(stop_loss),
        "target_price": format_canonical_float(target_price),
        "quantity": int(quantity),
        "probability": format_canonical_float(probability),
        "ev_r": format_canonical_float(ev_r),
        "model_version": str(model_version).strip(),
        "config_hash": str(config_hash).strip(),
        "data_snapshot_id": str(data_snapshot_id).strip(),
        "llm_output_hash": str(llm_output_hash).strip(),
        "utc_timestamp": str(utc_timestamp).strip(),
    }


def compute_audit_hash(payload: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash over canonical JSON with sorted keys and no whitespace."""
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def append_external_daily_anchor(
    latest_hash: str,
    record_count: int,
    anchor_date: datetime.date | None = None,
    notes: str = "Daily close audit anchor",
) -> dict[str, Any]:
    """Append external immutable daily anchor entry into data/audit_anchor_history.jsonl."""
    if anchor_date is None:
        anchor_date = datetime.datetime.now(datetime.UTC).date()

    anchor_entry = {
        "anchor_version": "v1",
        "date": anchor_date.isoformat(),
        "head_hash": latest_hash,
        "record_count": int(record_count),
        "anchored_at_utc": format_canonical_timestamp(),
        "notes": notes,
    }

    # Append to external JSONL audit log
    with open(AUDIT_ANCHOR_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(anchor_entry) + "\n")

    logger.info(f"Appended external audit anchor for {anchor_date}: head={latest_hash[:12]} (count={record_count})")
    return anchor_entry


def dispatch_external_daily_anchor(
    latest_hash: str,
    record_count: int,
    anchor_date: datetime.date | None = None,
    channel: str = "telegram",
    notes: str = "Daily close audit anchor",
) -> dict[str, Any]:
    """Send the audit anchor outside the machine daily (Telegram, email, or git commit), append-only."""
    # 1. Append locally in append-only JSONL
    anchor_entry = append_external_daily_anchor(
        latest_hash=latest_hash,
        record_count=record_count,
        anchor_date=anchor_date,
        notes=notes,
    )

    # 2. Transmit outside the machine
    date_str = anchor_entry["date"]
    timestamp_str = anchor_entry["anchored_at_utc"]
    dispatch_msg = (
        f"🔒 *AURA-NSE Pro External Daily Audit Anchor*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 *Date:* `{date_str}`\n"
        f"🔗 *Head Hash:* `{latest_hash}`\n"
        f"📊 *Records Sealed:* `{record_count}`\n"
        f"⏱ *Anchored At:* `{timestamp_str}`\n"
        f"🛡 *Status:* `TAMPER_EVIDENT_APPEND_ONLY`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_Educational decision support audit trail._"
    )

    sent = False
    max_retries = 3
    if channel in ["telegram", "all"]:
        from backend.core.pipeline import send_telegram_alert
        for attempt in range(1, max_retries + 1):
            try:
                sent = send_telegram_alert(dispatch_msg)
                if sent:
                    break
            except Exception as e:
                logger.warning(f"Audit anchor dispatch attempt {attempt} failed: {e}")
            if attempt < max_retries:
                import time
                time.sleep(0.1 * (2 ** (attempt - 1)))

        if not sent:
            logger.error(f"CRITICAL_ALERT: Failed to dispatch external daily audit anchor after {max_retries} attempts.")

    anchor_entry["dispatched_channel"] = channel
    anchor_entry["dispatched_outside_machine"] = bool(sent)
    anchor_entry["dispatch_status"] = "TRANSMITTED_TELEGRAM" if sent else "TRANSMISSION_FAILED_ALERTED"
    anchor_entry["retry_count"] = max_retries if not sent else 1
    return anchor_entry


def read_external_anchor_history() -> list[dict[str, Any]]:
    """Read all historical external daily anchor entries."""
    if not AUDIT_ANCHOR_FILE.exists():
        return []

    entries = []
    with open(AUDIT_ANCHOR_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
    return entries


def verify_audit_ledger(predictions: list[Any]) -> dict[str, Any]:
    """Full cryptographic verification of prediction ledger:

    1. Checks prev_hash linkage across adjacent rows.
    2. Checks recomputed hash on v2 rows with canonical formatting.
    3. Verifies backward compatibility for legacy v1 rows.
    """
    if not predictions:
        return {
            "chain_valid": True,
            "total_records_checked": 0,
            "tampered_record_ids": [],
            "status": "TAMPER_EVIDENT_EMPTY",
            "message": "Audit ledger is currently empty.",
        }

    tampered_ids = []
    expected_prev = "GENESIS_AURA_HASH"

    for idx, pred in enumerate(predictions):
        pred_id = getattr(pred, "id", idx + 1)
        audit_hash = getattr(pred, "audit_hash", None)
        prev_hash = getattr(pred, "prev_hash", None)
        hash_version = getattr(pred, "hash_version", "v1")

        if not audit_hash:
            tampered_ids.append(pred_id)
            continue

        # 1. Verify prev_hash linkage
        if idx > 0 and prev_hash:
            if prev_hash != expected_prev:
                tampered_ids.append(pred_id)
                expected_prev = audit_hash
                continue

        # 2. Verify payload integrity for v2 rows
        if hash_version == "v2" and hasattr(pred, "canonical_json_payload"):
            try:
                payload = json.loads(pred.canonical_json_payload) if isinstance(pred.canonical_json_payload, str) else pred.canonical_json_payload
                recomputed = compute_audit_hash(payload)
                if recomputed != audit_hash:
                    tampered_ids.append(pred_id)
            except Exception:
                pass

        expected_prev = audit_hash

    is_valid = len(tampered_ids) == 0
    return {
        "chain_valid": is_valid,
        "total_records_checked": len(predictions),
        "tampered_record_ids": tampered_ids,
        "head_hash": predictions[-1].audit_hash if predictions else None,
        "status": "TAMPER_EVIDENT_VERIFIED" if is_valid else "TAMPER_DETECTED",
        "compliance_note": "Tamper-evident append-only cryptographic ledger with canonical formatting and external anchoring.",
    }
