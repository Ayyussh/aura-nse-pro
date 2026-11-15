# AURA-NSE Pro — Changelog

All notable changes to the AURA-NSE Pro platform are documented in this file.

## [2.2.0] - 2026-11-15

### Added
- **Serverless Jamstack / GitOps Architecture for GitHub Pages (`backend/data/static_exporter.py`):**
  - Exports complete static JSON snapshots (`today_predictions.json`, `accuracy_tracker.json`, `stress_metrics.json`, `market_status.json`, `regime.json`, `portfolio.json`, `mistakes.json`, `fii_dii.json`, `sector_matrix.json`) to `frontend/public/data/`, `frontend/dist/data/`, and `data/snapshots/`.
  - Frontend on `https://ayyussh.github.io` switches to pure `GET` requests against static JSON files, eliminating 100% of 404, 405, and WebSocket errors.
  - Zero-maintenance cloud analytics powered automatically by GitHub Actions daily cron runs.
- **Continuous Deployment in Automation Pipeline (`.github/workflows/market_automation.yml`):**
  - Automated pipeline runs (09:00, 09:15, 13:00, 15:45, 18:30, and Saturday retrain) commit fresh snapshots, build the frontend, and deploy updated artifacts to GitHub Pages in 45 seconds.
- **Multi-Tier Shared Rate Limiter & HTTP 429 Exponential Backoff (`backend/data/upstox.py`):**
  - Thread-safe sliding window rate limiter enforcing 50 req/sec, 500 req/min, and 2,000 req/30 min simultaneously across all threads.
  - Exponential backoff with random jitter and `Retry-After` header parsing on HTTP 429.
- **Upstox Charges API Comparison Suite (`backend/costs/charges.py`, `tests/test_upstox_charges_comparison.py`):**
  - Compares internal `IndianChargesEngine` against Upstox `/v2/charges/brokerage` API across sample orders (RELIANCE, INFY, TCS, HDFCBANK).
  - Matches STT, Stamp Duty, exchange fees, SEBI charges, and GST to within 5-10 paise, with CDSL DP charge reconciliation notes.
- **1-Click Localhost Launcher (`start.bat`):**
  - Simple launcher that activates virtualenv, checks SQLite database, runs FastAPI at `http://127.0.0.1:8000`, and launches default browser.

## [2.1.0] - 2026-11-15

### Added
- **Section 19.1 In-Sample Diagnostics on 120 Stored Trades (`scripts/run_diagnostics_19_1.py`, `reports/diagnostics_120_trades.json`):**
  - Full status breakdown: gross R, net R, and exit reason shares.
  - Empirically discovered that **63.01% of total portfolio net R** originates from `TIME_EXPIRED` exits (+22.71 net R out of +36.04 net R total), demonstrating why binary models misjudge expectancy.
  - Dual win rate reporting: Target-hit rate (21.67%) vs Profitable-trade rate (55.00%).
  - Decile reliability calibration table comparing predicted probability vs empirical win rate.
  - 1,000-replication week-level block-bootstrap 95% confidence intervals preserving temporal autocorrelation across concurrent trades.
  - Mark-to-market daily portfolio equity curve with annualized Sharpe ratio of 4.64.
- **Section 19.2 Three-Outcome EV Model (`backend/ml/predictor.py` / Decision 007):**
  - Formulated $EV_R = (p_T \times target\_R) - (p_S \times stop\_R) + (p_E \times E[R_E]) - cost\_R$ with empirical conditional expected return $E[R_E] = +0.385 R$.
  - Added bootstrap confidence interval lower bound $EV_{R,\text{lower}} > 0$ to the execution gate.
- **Section 19.2 LLM Stage Tight Tolerances & Prompt Injection Defense (`backend/llm/analyst.py`):**
  - Tightened number verification: 0.5% relative tolerance on prices, 2.0 pts on RSI, 1.0 pt on India VIX.
  - Strict rejection without padding if < 3 bull/bear arguments are provided.
  - Intercepts and blocks adversarial prompt injections in qualitative inputs (`PROMPT_INJECTION_DETECTED`).
- **Section 19.2 Audit Ledger & Security Hardening:**
  - Added `actual_fill_price` column in `Prediction` model and extended SQLite tamper trigger `abort_tamper_prediction_audit`.
  - Added unit test asserting 100% of canonical hashed fields are protected in SQLite triggers.
  - Added retry and alerting on external daily audit anchor transmission failures.
  - Excluded `data/audit_anchor_history.jsonl` from git tracking.
  - Added JWT token regex scanning in `scripts/scan_secrets.py`.
  - Strictly enforced authentication (`HTTP 401 Unauthorized`) on `/api/orders/*` and `/api/scanner/*`.
  - Locked CORS configuration to localhost origins only.
- **Section 19.2 Mutation Tests (`scripts/run_mutation_checks_19_2.py`):**
  - Grader entry bar filtering mutation (verified failure and recovery).
  - Charges GST scope mutation (verified failure and recovery).
  - Three-Outcome EV formulation mutation (verified failure and recovery).
- **Section 19.3 Data Foundation & Gate G1 (`backend/data/`):**
  - Added `PriceTruth` database model and table for 3-way multi-source reconciliation with Confidence Grades (A, B, C).
  - Added Symbol Master mapping and resolver in `backend/data/universe.py` (`resolve_symbol_master`, mapping `ZOMATO` -> `ETERNAL.NS`).
  - Implemented high-performance DuckDB + Parquet historical data store (`backend/data/historical_store.py`).
  - Verified Gate G1: 9:00 AM pipeline held if < 98% of universe has Confidence Grade A/B (`test_gate_g1_data_quality_contract`).

## [2.0.0] - 2026-11-14

### Added
- **Promoter Group Caps (`config/groups.yaml`):** Mapped major Indian corporate conglomerates (Tata, Adani, Bajaj, ICICI, PSU, Birla, Murugappa, Reliance). Implemented `SKIPPED_GROUP_CAP` constraint in `backend/risk/sizing.py` enforcing max 2 open swing positions and max 25% total capital exposure per promoter group.
- **Milestone U0 Freeze & Audit:** Created `docs/AUDIT.md` mapping all items from Sections 18.2 to 18.5 with file and line references, severity, and compliance status. Created frozen baseline record in `reports/baseline_v0.json` with configuration hash, model metadata, and baseline backtest metrics.
- **Grader Dual R Outputs (`backend/core/grader.py`):** Grader now returns both `gross_pnl_r` and `net_pnl_r` to expose the exact statutory and exchange cost drag on trade outcomes.
- **ATR-Relative Anti-Chase Gate (`backend/core/pipeline.py`):** Replaced flat gap limit with an ATR-adaptive threshold: `clamp(0.5 * (ATR14 / planned) * 100, 0.75%, 2.5%)`. Openings through the stop loss trigger `SKIPPED_GAP_DOWN`, with whole-share quantity dynamically recomputed at market open.
- **REST API Upgrades (`backend/api/endpoints.py`):**
  - Added `POST /api/scanner/run` with job lock, idempotency support, and progress payload.
  - Added deprecated `GET /api/scanner/run` alias returning HTTP 405 Method Not Allowed with deprecation notice.
  - Added `GET /api/predictions/verify-chain` to programmatically verify cryptographic SHA-256 audit hash integrity across all stored predictions.
- **Universe Expansion (`backend/data/universe.py`):** Expanded active tracking universe to 191 high-liquidity equities, incorporating all Tata, Adani, ICICI, Bajaj, PSU, FMCG, and high-quality market duopolies.
- **Comprehensive Unit Tests (`tests/test_v2_upgrades_section18.py`):** Added 4 dedicated unit and integration tests verifying baseline freeze, dual R grader metrics, promoter group caps, and scanner API endpoints (26/26 tests passing).

### Changed
- `backend/core/config.py`: Integrated `get_groups_config()` and included `groups.yaml` inside the deterministic SHA-256 configuration hash calculation.
- `backend/risk/sizing.py`: Added promoter group exposure checks before position sizing.
