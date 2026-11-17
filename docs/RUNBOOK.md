# Operational Runbook & Failure-Mode Procedures (AURA-NSE Pro)

This runbook outlines operational procedures, failure-mode recovery steps, disaster recovery drills, and routine maintenance for AURA-NSE Pro.

---

## 1. Operating Architecture & Health Summary

- **Local Host:** Windows / Linux / macOS on loopback `127.0.0.1:8000`.
- **Database:** SQLite (`backend/aura_nse.db`) in WAL mode + DuckDB Data Lake (`data/aura_historical.duckdb`).
- **Telemetry & Logging:** Dual-sink logging to stdout and rotating files (`logs/aura.log`, 10MB x 5 backups).
- **Scheduler:** Daily pipeline triggers at 09:00 IST (pre-market plan), 09:20 IST (open execution & gap audit), 15:45 IST (EOD outcome grading), and 18:30 IST (nightly scan & ML update).

---

## 2. Failure Mode Procedures

### Incident 001: Upstox Access Token Expiry or Auth Failure
- **Symptom:** Log warning `Upstox token expires in X days` or HTTP 401/403 on historical/live bar requests.
- **Root Cause:** Upstox API v2 access tokens expire after 365 days or when invalidated.
- **Automated Response:** The system logs an operational warning, disables the Upstox provider pipeline, and falls back to official NSE Bhavcopy and Yahoo Finance. Zero synthetic data is generated.
- **Remediation Steps:**
  1. Log in to [Upstox Developer Portal](https://developer.upstox.com/).
  2. Navigate to your registered app and click **Generate Access Token**.
  3. Update your `.env` file:
     ```env
     UPSTOX_ACCESS_TOKEN=your_new_token_here
     ```
  4. Verify connection using the test CLI:
     ```powershell
     .venv\Scripts\python -c "from backend.data.provider import data_provider; print(data_provider.check_upstox_health())"
     ```

---

### Incident 002: Bhavcopy Download or Upstream NSE Outage
- **Symptom:** HTTP 403, 502, or timeout when fetching daily bhavcopy from `archives.nseindia.com`.
- **Root Cause:** NSE server maintenance, Akamai CDN rate-limiting, or exchange network downtime.
- **Automated Response:**
  1. The system checks local DuckDB data lake (`data/aura_historical.duckdb`) for existing cached bars.
  2. Attempts secondary mirror download with custom user-agent rotation.
  3. If unavailable, flags data state as `STALE_DATA_BADGE` and defers non-critical EOD grading until the 18:30 IST scheduled retry.
- **Remediation Steps:**
  1. Manually test Bhavcopy fetch:
     ```powershell
     .venv\Scripts\python -c "from backend.data.bhavcopy import bhavcopy_engine; import datetime; print(bhavcopy_engine.download_and_parse_bhavcopy(datetime.date.today()))"
     ```
  2. If NSE website changed archive URL format, update `NSE_BHAVCOPY_BASE_URL` in `backend/data/bhavcopy.py`.

---

### Incident 003: LLM Quota Exhaustion (HTTP 429) & Provider Failover
- **Symptom:** Log message `Gemini rate limit 429: Activating 60-minute cooldown`.
- **Root Cause:** Daily free-tier or per-minute token quota exceeded on active Gemini model.
- **Automated Response:**
  1. `LLMRouter` marks the exhausted model in cooling status for 3600 seconds.
  2. Dynamically routes qualitative audit to next available model (e.g. `gemini-2.5-flash` &rarr; `gemini-2.5-pro` &rarr; Groq &rarr; OpenRouter &rarr; Ollama).
  3. If all LLM providers fail, trade plan status is set to `NOT_AUDITED` and position sizing is halved (or skipped based on `strategy.yaml` rule). Execution does not halt.
- **Remediation Steps:**
  1. Open Key Vault in frontend or set alternative provider API key in `.env`:
     ```env
     GROQ_API_KEY=gsk_...
     OPENROUTER_API_KEY=sk-or-...
     ```
  2. Run vault diagnostic:
     ```powershell
     .venv\Scripts\python -c "from backend.llm.router import llm_router; print(llm_router.discover_available_models())"
     ```

---

### Incident 004: SQLite Database Tampering / Integrity Violation / Corruption
- **Symptom:** `AuditIntegrityError: Hash mismatch detected on prediction ID #X` or SQLite `database disk image is malformed`.
- **Root Cause:** Unsanctioned manual write to database file, power loss during write, or disk hardware sector error.
- **Automated Response:**
  1. Audit ledger halts automated trade approvals.
  2. High-priority alert dispatched to Telegram owner chat.
- **Remediation Steps:**
  1. Run SQLite integrity check:
     ```powershell
     .venv\Scripts\python -c "import sqlite3; con = sqlite3.connect('backend/aura_nse.db'); print(con.execute('PRAGMA integrity_check').fetchall())"
     ```
  2. Run audit ledger verification:
     ```powershell
     .venv\Scripts\python -c "from backend.core.audit_ledger import audit_ledger; print(audit_ledger.verify_ledger_integrity())"
     ```
  3. If corrupt, restore from the latest verified snapshot in `backups/`:
     ```powershell
     Copy-Item -Path (Get-ChildItem backups\aura_nse_*.db | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName -Destination backend\aura_nse.db -Force
     ```

---

### Incident 005: Low Disk Space Alert (< 2GB or < 10% Free)
- **Symptom:** Log warning `CRITICAL: Free disk space on drive C: is below 2.00 GB`.
- **Root Cause:** Accumulation of old log files, raw Bhavcopy ZIP archives, or temporary cache.
- **Remediation Steps:**
  1. Clean old logs:
     ```powershell
     Get-ChildItem logs\*.log.* | Remove-Item -Force
     ```
  2. Vacuum DuckDB and SQLite databases:
     ```powershell
     .venv\Scripts\python -c "import sqlite3, duckdb; sqlite3.connect('backend/aura_nse.db').execute('VACUUM'); duckdb.connect('data/aura_historical.duckdb').execute('VACUUM')"
     ```

---

### Incident 006: Telegram Bot Dispatch Failure or Network Timeout
- **Symptom:** Log warning `Telegram notification failed: Connection reset / 401 Unauthorized`.
- **Root Cause:** Invalid `TELEGRAM_BOT_TOKEN`, revoked bot access, or ISP DNS block on `api.telegram.org`.
- **Automated Response:** Notification failure is logged without blocking core trading pipeline or corrupting database transactions.
- **Remediation Steps:**
  1. Test Telegram bot token and chat ID via script:
     ```powershell
     .venv\Scripts\python -c "from backend.alerts.telegram import send_telegram_alert; import asyncio; asyncio.run(send_telegram_alert('AURA Runbook Diagnostic Test'))"
     ```
  2. If blocked by ISP, configure HTTPS proxy in `TELEGRAM_PROXY_URL`.

---

## 3. Disaster Recovery Drill (Backup & Restore)

### Automated Daily Backup
The system creates compressed, timestamped backups of `backend/aura_nse.db` and `data/aura_historical.duckdb` daily at 23:00 IST into `backups/`.

### Verified Restore Procedure
To test restore capability or recover from disaster:
1. Stop running backend process (`Ctrl+C` or task kill).
2. Execute automated restore test:
   ```powershell
   .venv\Scripts\python -c "
   import shutil, os, glob
   backups = sorted(glob.glob('backups/aura_nse_*.db'))
   if backups:
       latest = backups[-1]
       shutil.copy2(latest, 'backend/aura_nse.db')
       print(f'Successfully restored from {latest}')
   else:
       print('No backup found')
   "
   ```
3. Run test suite to verify restored database schema and integrity:
   ```powershell
   .venv\Scripts\pytest tests/test_coverage_21_1_8.py
   ```

---

## 4. Routine Maintenance Schedule

| Frequency | Task | Command / Script | Verification Target |
|-----------|------|------------------|---------------------|
| Daily (08:00) | Token expiry check | `job_check_token_expiry` | Alert if $\le 30$ days left |
| Daily (15:45) | Outcome grading | `grade_pending_predictions` | All active trades resolved |
| Weekly (Sat 10:30) | Symbol & corporate action sync | `job_weekly_symbol_and_corporate_action_check` | Zero unadjusted splits |
| Weekly (Sun 12:00) | Shadow Scorecard export | `scripts/shadow_scorecard.py` | `reports/shadow_scorecard_weekly.json` |
| Monthly | SQLite / DuckDB vacuum | `VACUUM` commands | DB sizes $< 100$ MB |
