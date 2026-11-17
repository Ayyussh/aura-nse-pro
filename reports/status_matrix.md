# AURA-NSE Pro — Specification Status Matrix (v2 / Sections 18, 19, 20)

**Generated:** 2026-11-15T23:45:00 IST  
**Environment:** Windows 10, Python 3.11.17 (`.venv`), Git 2.43.0, Node v22.22.2, Vite 6.4.6, DuckDB 2.0.0  
**Test Suite Status:** 116 / 116 passing (100%) across all milestone suites  
**Security Status:** Zero secrets committed (`scripts/scan_secrets.py` CLEAN, `.env` untracked, zero JWT payloads in reports)  
**Verification Target:** `powershell -ExecutionPolicy Bypass -File scripts/verify.ps1` (Steps 1–6 PASSED with Holdout SEALED)  

---

## 1. Executive Summary & Honest Status Breakdown

| Status Tag | Count | Meaning |
|---|---|---|
| **DONE** | 24 | Fully implemented, mathematically audited, verified against real market data, 100% tests passing |
| **PARTIAL** | 0 | All data foundation items fully backfilled across 505 instruments (562,319 clean bars in DuckDB) |
| **BLOCKED** | 1 | Strictly sealed pending explicit investor/user authorization (Holdout Partition: 2025-09-01 to 2026-11-13) |

---

## 2. Section 18: System Upgrades (U0 - U8)

| Item | Requirement | Status | Evidence (Code / Test / Artifact) |
|---|---|---|---|
| **18.1 U0** | Audit & freeze baseline_v0, store model files, rules, metrics | **DONE** | `docs/AUDIT.md`, `reports/baseline_v0.json`, git tag `baseline_v0` |
| **18.2 U1.1** | Grader: evaluate bars strictly after entry, stop-first rule on ties, gap fills at open, TIME_EXPIRED on day N, real charges net R, provisional 15:45 + 18:30 recon | **DONE** | `backend/core/grader.py`, `tests/test_grader_synthetic_bars.py`, `tests/test_v2_upgrades_section18.py` |
| **18.2 U1.2** | Anti-chase gate: clamp(0.5 x ATR14, 0.75%, 2.5%), SKIPPED_GAP_DOWN, quantity recomputed from actual open | **DONE** | `backend/core/pipeline.py` (`evaluate_open_gap_and_adjust_quantity`), `tests/test_v2_upgrades_section18.py` |
| **18.2 U1.3** | EV formula: cost_R from charges engine + slippage tiers, target_R = (Tgt-Entry)/(Entry-Stop), EV_R >= 0.20, p >= 0.45 | **DONE** | `backend/ml/predictor.py` (`compute_ev_r`), `tests/test_v2_upgrades_section18.py` |
| **18.2 U1.4** | Calibration metrics: Brier, Brier skill score (BSS = 1 - Brier/Brier_base), AUC, log loss, reliability curve, decile realized win rate, SUSPECTED_LEAKAGE guard | **DONE** | `backend/ml/evaluator.py`, `reports/validation_reliability_report.json`, `tests/test_v2_upgrades_section18.py` |
| **18.2 U1.5** | Audit ledger: canonical JSON SHA-256, prev_hash chaining, SQLite triggers rejecting UPDATE/DELETE, verify_chain endpoint, external daily anchor | **DONE** | `backend/db/audit.py`, `backend/db/init_db.py`, `tests/test_audit_improvements.py` |
| **18.2 U1.6** | Demo data: quarantined from production, GitHub Pages marked DEMO, basket export disabled | **DONE** | `frontend/src/utils/demoData.ts`, `frontend/src/components/CommandCenter.tsx`, `backend/api/endpoints.py` |
| **18.2 U1.7** | LLM stage: 3 bull, 3 bear, invalidation, untrusted news, number check against data layer, fallback NOT_AUDITED | **DONE** | `backend/llm/analyst.py`, `tests/test_v2_upgrades_section18.py` |
| **18.2 U1.8** | API: POST /api/scanner/run with job lock & idempotency key, SSE progress stream, deprecated GET alias returning 405 | **DONE** | `backend/api/endpoints.py`, `tests/test_v2_upgrades_section18.py` |
| **18.2 U1.9** | Regime machine: GREEN/YELLOW/RED config thresholds, 2 consecutive closes to change, shadow scanning in RED, breadth input | **DONE** | `backend/strategies/regime.py`, `tests/test_v2_upgrades_section18.py` |
| **18.2 U1.10**| Kite basket & GTT export: gated by open check, entered trades only, schema verified | **DONE** | `backend/api/endpoints.py`, `tests/test_v2_upgrades_section18.py` |
| **18.3 U2** | Data foundation: NSE archives, Upstox API, yfinance fallback, price_truth table A/B/C, DuckDB/Parquet store, symbol master, group caps (groups.yaml) | **DONE** | Upstox multi-tier limiter active; 505 instruments (562,319 clean bars) backfilled in DuckDB; `reports/backfill_status_report.json` |
| **18.4 U3** | Replay engine & scorecards: no-lookahead replay, full candidate logging (taken=false), segregated tables (BACKTEST/SHADOW/LIVE), walk-forward scorecards | **DONE** | `backend/strategies/replay.py`, `reports/replay_scorecard_v0.json`, `reports/full_universe_candidates_replay_report.json` (29,572 candidates) |
| **18.5 U4** | Self-learning safety: champion/challenger, weekly retraining, proposal-only mistake rules (n >= 30, no holdout harm), CI leakage tests | **DONE** | `backend/ml/retrain.py`, `data/mistake_rules.json`, `tests/test_self_improving_ml.py` |
| **18.6 U5** | Indicator batches A-D: rank normalization, ablations on validation, 25-feature cap, event filters as rules, Mansfield RS documented | **DONE** | `backend/ml/features.py`, `backend/strategies/indicators.py`, `reports/indicator_ablation_report.json`, `tests/test_indicator_batches_ablation.py` |
| **18.7 U6** | Portfolio, costs, tax: charges config (STT 0.1%, stamp duty 0.015%, GST on brokerage+txn, DP ₹15.93), tax engine (STCG 20%+cess, LTCG 12.5%>1.25L), sizing from actual open | **DONE** | `backend/costs/charges.py`, `backend/tax/capital_gains.py`, `backend/risk/sizing.py`, `backend/db/fill_events.py`, `tests/test_milestone_2_costs_tax_risk.py` |
| **18.8 U7** | Operations: APScheduler persistent store, NSE holiday calendar, dead-man's heartbeat, daily SQLite backup with restore test, encrypted vault | **DONE** | `backend/jobs/scheduler.py`, `scripts/backup_db.py`, `backend/data/holiday_calendar.py` |
| **18.9 U8** | Acceptance & final holdout comparison report | **BLOCKED** | Holdout partition (2025-09-01 to 2026-11-13) strictly locked per Directive #5. Awaiting user authorization. |

---

## 3. Section 19: Completion Brief (19.1 - 19.9)

| Item | Requirement | Status | Evidence (Code / Test / Artifact) |
|---|---|---|---|
| **19.1** | In-sample diagnostics on 120 stored trades: gross/net R by status, net R from time-expiry, dual win definition, decile reliability, block-bootstrap CI, daily rupee equity curve | **DONE** | `scripts/run_clean_recomputation.py`, `reports/diagnostics_120_trades.json`, `tests/test_section19_diagnostics.py` |
| **19.2.1** | Three-outcome EV model: p_T, p_S, p_E with empirical E[R_E], EV lower-bound gate > 0 | **DONE** | `backend/ml/predictor.py`, `backend/ml/setup_priors.py`, `tests/test_section19_diagnostics.py` |
| **19.2.2** | LLM stage: relative tolerances (0.5% price, 2 pts RSI, 1 pt VIX), reject if < 3 bull/bear, prompt-injection defense | **DONE** | `backend/llm/analyst.py`, `tests/test_section19_diagnostics.py` |
| **19.2.3** | Audit: trigger covers all hashed fields test, `actual_fill_price` column, anchor retry/alert, anchor history untracked | **DONE** | `backend/db/init_db.py`, `backend/db/fill_events.py`, `tests/test_mutation_guards.py` |
| **19.2.4** | Endpoints auth: 401 on unauthenticated `/api/orders/*`, `/api/vault/*`, `/api/scanner/*`, localhost binding, locked CORS | **DONE** | `backend/api/auth.py`, `backend/api/endpoints.py`, `backend/main.py`, `tests/test_mutation_guards.py` |
| **19.2.5** | Secrets scan: JWT regex scanning, .env untracked, zero tokens in reports | **DONE** | `scripts/scan_secrets.py`, `.gitignore` |
| **19.2.6** | Mutation checks: 6 mutations tested and verified failing test cases | **DONE** | `scripts/run_mutation_checks_19_2.py`, `tests/test_mutation_guards.py` |
| **19.3** | Data foundation (Gate G1): Upstox smoke test, NSE archive pipeline, 3-source reconciliation, corporate-action ledger, DuckDB backfill, universe | **DONE** | `reports/reconciliation_mismatch_report.json` (100% Grade A/B agreement), `reports/bhavcopy_yfinance_check_report.json` (100% exact matches across YFINANCE_HIST rows), `reports/stored_trades_contamination_report.json` (0 contaminated trades) |
| **19.4** | Replay engine & scorecards (Gate G2): day D known-data assertion, train/val splits, scorecards with bootstrap intervals | **DONE** | `backend/strategies/replay.py`, `reports/replay_scorecard_v0.json`, `reports/full_universe_candidates_replay_report.json` |
| **19.5** | Self-learning safety: champion/challenger promotion gate, weekly cadence, proposal-only rules with replay evidence | **DONE** | `backend/ml/retrain.py`, `data/mistake_rules.json`, `tests/test_self_improving_ml.py` |
| **19.6** | Indicators A-D ablations on validation data | **DONE** | `backend/ml/features.py`, `reports/indicator_ablation_report.json`, `tests/test_indicator_batches_ablation.py` |
| **19.7** | Portfolio/tax audit & holdout lock verification | **DONE** | `backend/tax/capital_gains.py`, `scripts/verify.ps1` (Holdout strictly locked) |
| **19.8** | Persistent scheduler, 5-job daily routine, dead-man's switch | **DONE** | `backend/jobs/scheduler.py`, `scripts/run_shadow.bat`, Windows task `\AURA_NSE_Daily_Shadow` |
| **19.9** | Final verification script (`scripts/verify.ps1`, `make verify`) | **DONE** | `scripts/verify.ps1`, `Makefile` |

---

## 4. Section 20: Master Prompt Execution Phases (P0 - P8)

| Phase | Description | Status | Current Evidence / Next Action |
|---|---|---|---|
| **P0** | Environment, test baseline, Upstox smoke test, status matrix | **DONE** | `reports/status_matrix.md` updated; Upstox token active (365 days remaining) |
| **P1** | Truth fixes: setup priors provenance, G1 real data reconciliation, symbol master (TMPV, TMCV, VEDL, HDFC), contamination check, NIFTY comparator | **DONE** | `backend/ml/setup_priors.py`, `reports/reconciliation_mismatch_report.json`, `reports/bhavcopy_yfinance_check_report.json` (100% exact match), `reports/priors_provenance_clean.json` |
| **P2** | Data foundation complete (Gate G1): multi-tier limiter with state persistence, Upstox instruments, DuckDB & Parquet store, 562,319 bars backfill | **DONE** | DuckDB store holds 562,319 clean bars across 505 instruments (501 equities + 4 indices, 0 synthetic). `reports/backfill_status_report.json` |
| **P3** | Replay engine & scorecards (Gate G2): train/val splits, bootstrap scorecards, rupee equity curve, determinism verified | **DONE** | `backend/strategies/replay.py`, `reports/full_universe_candidates_replay_report.json` (29,572 candidates audited) |
| **P4** | Learning safety & ML decision: champion/challenger, 3-class EV model, out-of-sample skill gate, mistake proposals (N >= 30) | **DONE** | `backend/ml/predictor.py`, `backend/ml/retrain.py`, `reports/ml_purged_validation_report.json` (ML kept OFF) |
| **P5** | Indicator batches A-D with validation ablations, 25-feature cap, cross-sectional rank normalization, Mansfield RS | **DONE** | `backend/ml/features.py`, `backend/strategies/indicators.py`, `reports/indicator_ablation_report.json`, `tests/test_indicator_batches_ablation.py` |
| **P6** | Portfolio, costs, tax, journal, TradeFillEvent append-only chained event ledger with SQLite immutability triggers | **DONE** | `backend/db/models.py`, `backend/db/fill_events.py`, `backend/tax/capital_gains.py`, `tests/test_mutation_guards.py` |
| **P7** | Operations, security, public demo, loopback 127.0.0.1 binding, 401 on protected endpoints, Windows Task Scheduler shadow runner, heartbeat ping | **DONE** | `backend/main.py`, `backend/api/auth.py`, `backend/api/endpoints.py`, `scripts/run_shadow.bat`, Windows task `AURA_NSE_Daily_Shadow` active |
| **P8** | Single holdout evaluation on clean real data | **BLOCKED** | Strictly sealed per User Directive #5. Can only be opened with explicit user approval after research phase is completed. |
