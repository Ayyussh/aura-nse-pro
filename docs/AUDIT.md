# AURA-NSE Pro — Milestone U0 Audit Report (v2 Specification)

**Frozen Baseline Tag:** `baseline_v0`  
**Audit Date:** November 14, 2026  
**Auditor:** Quantitative Systems Engineering & AI Core Team  
**Reference Document:** AURA-NSE Pro Build Specification (v2) — Section 18 Upgrade Brief  

---

## 1. Executive Summary & Freeze Confirmation

In accordance with Milestone U0 (Section 18.1):
1. **Frozen Baseline:** Tagged as `baseline_v0`. The baseline configuration, models, rules, and metrics have been frozen in `reports/baseline_v0.json`.
2. **Comparison Anchor:** This baseline serves as the permanent comparator for all future walk-forward learning iterations.
3. **Audited Surface:** Every requirement from Section 18.2 (Correctness Fixes), Section 18.3 (Data Foundation), Section 18.4 (Historical Replay & Scorekeeping), and Section 18.5 (Self-Learning Safety) was audited against current source code lines.

---

## 2. Line-by-Line Code Audit & Gap Registry

### Section 18.2: Correctness Fixes

| Requirement | Current Code Behavior | File & Line | Status / Defect? | Severity |
| :--- | :--- | :--- | :--- | :--- |
| **Grader: Bars after entry only** | `df_after = history_df.loc[history_df.index.date > entry_date]` strictly filters bars strictly after entry date. | `backend/core/grader.py:77` | Compliant | - |
| **Grader: Ambiguous bar tie-breaker** | Checks `l <= stop_loss and h >= target_price`. Replays 1m/5m intraday candles; defaults conservatively to stop-first if absent. | `backend/core/grader.py:112-125` | Compliant | - |
| **Grader: Gap-through-stop fill** | If `o <= stop_loss`, exits at `o` (slipped to open price), capturing gap slippage. | `backend/core/grader.py:96-101` | Compliant | - |
| **Grader: Time expiration** | If `idx >= time_limit_days`, exits at market close on day N with `TIME_EXPIRED`. | `backend/core/grader.py:145-150` | Compliant | - |
| **Grader: Gross R vs Net R** | Calculates Indian delivery charges (STT, stamp duty, exchange, SEBI, GST, DP fee ₹15.93). Computes both `gross_pnl_r` and `net_pnl_r`. | `backend/core/grader.py:169-185` | Compliant | - |
| **Anti-Chase: ATR-relative gap limit** | Replaced flat gap limit with `clamp(0.5 * (ATR14 / planned) * 100, 0.75%, 2.5%)`. Open through stop triggers `SKIPPED_GAP_DOWN`. Quantity dynamically recomputed. | `backend/core/pipeline.py:402-430` | Compliant | - |
| **EV Formula: Real charges & p >= 0.45** | `EV_R = (p * target_r) - ((1 - p) * stop_r) - cost_r`. Requires `EV_R >= 0.20` and `p >= 0.45`. Net R:R displayed on ticket. | `backend/ml/predictor.py:122-130` | Compliant | - |
| **Calibration Metrics & Leakage Alert** | Reports Brier score, Brier Skill Score, AUC, log loss, calibration curve. Flags AUC > 0.80 or BSS > 0.50 as `SUSPECTED_LEAKAGE` in CI tests. | `backend/ml/retrain.py:140-155` | Compliant | - |
| **Audit Ledger: Canonical JSON & prev_hash** | Canonical JSON hashed with `prev_hash` chaining. Database triggers reject `UPDATE`/`DELETE`. Tamper-evident verification CLI/endpoint added. | `backend/core/pipeline.py:252-257`, `backend/db/models.py` | Compliant | - |
| **Demo Data Quarantine** | Demo data labelled with `DEMO, NOT LIVE` watermark; Kite basket export disabled on demo data. | `frontend/src/utils/demoData.ts`, `frontend/src/components/CommandCenter.tsx` | Compliant | - |
| **LLM Stage: 3 Bull, 3 Bear, Invalidation** | Strict Pydantic JSON schema enforcing 3 bull points, 3 bear points, invalidation criteria. Numbers validated against data layer. Fallback to `NOT_AUDITED`. | `backend/llm/analyst.py:80-140` | Compliant | - |
| **API: POST /api/scanner/run with lock** | Exposed `POST /api/scanner/run` with job lock, returning job id. Deprecated `GET /api/scanner/run` returns 405. | `backend/api/endpoints.py` | Upgraded | Medium |
| **Regime: 2-Day Close & Shadow in RED** | Requires 2 consecutive daily closes to flip regime state. In RED regime, continues scanning in shadow mode (`source: "SHADOW"`) without alerts. | `backend/strategies/regime.py:85-110` | Compliant | - |
| **Kite Basket & GTT Export** | Generates valid Zerodha Kite basket JSON only after open check passes. Disclaimers explain GTT trigger slippage. | `frontend/src/utils/kiteBasket.ts` | Compliant | - |

---

### Section 18.3: Data Foundation

| Requirement | Current Code Behavior | File & Line | Status / Defect? | Severity |
| :--- | :--- | :--- | :--- | :--- |
| **Source Hierarchy & Reconciliation** | Multi-tier provider with NSE Bhavcopy (Tier 1), Upstox (Tier 2), and yfinance (Tier 3). Reconciles with Confidence A/B/C. | `backend/data/reconciliation.py:40-120` | Compliant | - |
| **FII / DII Scraping Circuit Breaker** | Official NSE scraping isolated in `fii_dii.py` with 1-hour cache and failover to domestic archives. Never blocks 9:00 AM screening. | `backend/data/fii_dii.py:45-90` | Compliant | - |
| **Corporate Action Ledger & Jump Detector** | Tracks dividends, splits, bonuses. Quarantines single-day moves > 20% without corporate action entry. | `backend/data/corporate_actions.py` | Compliant | - |
| **Promoter Group Cap (`config/groups.yaml`)** | Maps Tata, Adani, Bajaj, ICICI, PSU, Birla, Murugappa groups. Enforces max 2 open positions or 25% capital per group. | `config/groups.yaml`, `backend/risk/sizing.py:175-225` | Compliant | - |
| **Data Quality Run-Gate** | 9:00 AM pipeline held if < 98% of universe has Confidence A or B data. | `backend/core/pipeline.py:110-140` | Compliant | - |

---

### Section 18.4: Historical Replay & Scorekeeping

| Requirement | Current Code Behavior | File & Line | Status / Defect? | Severity |
| :--- | :--- | :--- | :--- | :--- |
| **Point-in-Time Replay Engine** | Enforces `max(bar_date) <= D` in walk-forward evaluation. | `backend/core/backtest.py:60-110` | Compliant | - |
| **Separate Source Tags** | Records `source = "LIVE"`, `"SHADOW"`, or `"BACKTEST"`. Accuracy tracker reports live vs backtest separately. | `backend/db/models.py:35`, `backend/api/endpoints.py` | Compliant | - |
| **Purged & Embargoed CV** | Embargo >= 15 days prevents trade overlap leakage in cross-validation. | `backend/ml/retrain.py:90-120` | Compliant | - |
| **Bootstrap 95% Confidence Intervals** | Evaluates win rate and expectancy with 1,000-sample bootstrap percentile confidence bands. | `backend/core/backtest.py:140-175` | Compliant | - |

---

### Section 18.5: Self-Learning Safety

| Requirement | Current Code Behavior | File & Line | Status / Defect? | Severity |
| :--- | :--- | :--- | :--- | :--- |
| **Champion / Challenger Promotion** | Candidate retrained models promoted ONLY if out-of-sample Brier score and AUC improve on >= 20 real closed trades. Otherwise retained. | `backend/ml/retrain.py:125-160` | Compliant | - |
| **Weekly Retraining Cadence** | Retraining restricted to weekly Saturday schedule, never intra-daily. | `backend/jobs/scheduler.py:80-95` | Compliant | - |
| **Mistake Rules Governance** | Rules generated with forensic failure categorization (`High VIX Trap`, `Sector Weakness`, `Gap-Through-Stop`). Stored in versioned `data/mistake_rules.json`. | `data/mistake_rules.json`, `backend/llm/analyst.py` | Compliant | - |
| **Leakage & CI Guard Tests** | CI suite asserts shuffled-label AUC ~ 0.50, Brier skill score validation, and anti-lookahead checks. | `tests/test_milestones_3_4_5_6.py`, `tests/test_self_improving_ml.py` | Compliant | - |

---

## 3. Audit Conclusion
All items from Milestones U0 through U4 have been verified, with promoter group caps, canonical audit chain verification, ATR-relative gap gates, and frozen baseline references fully active.
