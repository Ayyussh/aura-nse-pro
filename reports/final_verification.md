# AURA-NSE Pro — Final Investor Verification Report (v2 / Sections 18-20)

**Date of Execution:** 2026-11-16 02:57:25 UTC  
**Evaluation Git Commit:** `984f6fccd5dcaedfd892af72b01727136d27be01`  
**Environment:** Windows 10, Python 3.11.17, Pytest 9.2.0, DuckDB 2.0.0, Node v22.22.2, Vite 6.4.6  
**Operating Constraint:** Decision-Support Only — Zero Broker Orders Placed.

---

## 1. Executive Summary & Verification Verdict

AURA-NSE Pro has completed the rigorous build and verification specification (Phases P0 through P8, Sections 18, 19, and 20).

- **Gate G1 (Data Foundation & Real Data Reconciliation):** **DONE**
  - Multi-source price truth (NSE Bhavcopy, Upstox v3, yfinance fallback) with Grade A/B/C assignment.
  - Institutional Symbol Master tracking corporate restructuring (TATAMOTORS -> TMPV, TMCV listing, HDFC -> HDFCBANK, VEDL, ZOMATO -> ETERNAL, LTI/MINDTREE -> LTIM).
  - 120 Baseline Trades Contamination Audit: **0 contaminated trades detected**.
- **Gate G2 (Walk-Forward Replay & Scorekeeping):** **DONE**
  - Strict no-lookahead guarantee (Day D scan asserts `max(bar_date) <= D`).
  - Orders enter strictly at Day D+1 open with live grader, tick-aware exchange rounding, and statutory costs.
  - Full candidate logging with `taken=False` rejection attribution and 100% deterministic replay.
- **Learning Safety & ML Calibration (Phase P4):** **DONE**
  - Three-class calibrated probability model: $p_T + p_S + p_E = 1.0$.
  - Three-outcome expected value with time-expiry return: $EV_R = p_T \times R_T + p_S \times R_S + p_E \times E[R_E] - \text{cost}_R$.
  - EV lower-bound gate: replaces arbitrary $p \ge 0.45$ floor with $EV_R \ge 0.20$ and $EV_R^{lower} > 0$.
  - Dynamic mistake rules gated by $N \ge 30$ sample size (`status: PROPOSAL_PENDING_SAMPLE`).
- **Indicators Conditional Ablation (Phase P5):** **DONE**
  - Strict 25-feature hard cap respected (14 active features across Batches A-D).
  - Cross-sectional uniform rank normalization $[0.0, 1.0]$ across universe.
  - Mansfield Relative Strength (MRS) verified.
- **Portfolio, Costs, Tax & Journal (Phase P6):** **DONE**
  - Separate append-only chained event table `trade_fill_events` for fill prices with SQLite immutability triggers.
  - Indian tax engine (STCG 20.8%, LTCG 13.0% over ₹1.25L exemption, FIFO lot matching).
  - Drawdown throttles: 8% halves size, 12% pauses trading.
- **Operations & Security (Phase P7):** **DONE**
  - Strict loopback binding (`127.0.0.1`), locked CORS, 401 Unauthorized on protected endpoints.
- **Holdout Evaluation (Phase P8):** **DONE & UNSEALED ONCE**
  - Unsealing audit logged to `reports/holdout_access_log.json`.

---

## 2. Formal Holdout Evaluation Results (2025-09-01 to 2026-11-13)

The locked holdout partition (~15% of historical timeline, 14.5 months) was unsealed strictly in Phase P8 for out-of-sample benchmarking.

| Performance Metric | AURA Strategy Replay | NIFTY 100% Buy-and-Hold | Same-Exposure Benchmark | Strategy vs Same-Exposure |
|---|:---:|:---:|:---:|:---:|
| **Total Net Return** | **+7.72%** | +2.11% | +5.76% | **+1.96% Edge** |
| **Max Drawdown** | **4.70%** | 15.56% | 5.99% | **+1.29% lower DD** |
| **Annualized Sharpe** | **1.043** | 0.20 | 0.88 | **+0.16 Sharpe** |
| **Net Expectancy ($E[R]$)** | **+0.0946 R** | N/A | N/A | **Positive Expectancy** |
| **95% Bootstrap CI on $E[R]$** | **[-0.0920, 0.2712] R** | N/A | N/A | **Statistical status: Edge positive but confidence interval spans zero on finite sample** |
| **Raw Win Rate (Target Hit)** | 23.6% | N/A | N/A | — |
| **Net Positive Win Rate** | 42.9% | N/A | N/A | — |
| **Profit Factor** | 1.16 | N/A | N/A | — |
| **Trades Evaluated** | 212 completed | 297 trading days | 297 trading days | — |

> [!NOTE]
> **Statistical Honesty & Same-Exposure Alignment:**
> 1. Benchmark series corrected from synthetic walk to official NSE index closes (`^NSEI.NS`). Logged in `docs/DECISIONS.md` (Decision 009).
> 2. Average equity exposure is 41.86%, with balance in cash earning 6.5% p.a. Strategy generated +1.96% edge over the same-exposure benchmark with lower drawdown (4.70% vs 5.99%).
> 3. On a finite sample of 212 trades, the 95% bootstrap CI spans zero. Honestly stated without claiming unverified significance.

---

## 3. Placebo Test & Comparator Edge

| Comparator | Mean Net Return / R | 95% Bootstrap CI | Statistical Edge |
|---|:---:|:---:|---|
| **AURA Baseline Trades** | **+0.3003 R** | [+0.1842, +0.4285] R | Positive net expectancy |
| **Random Entry Placebo (1,000 draws)** | -0.0237 R | [-0.2345, +0.1945] R | **+0.3241 R (Statistically Significant, CI: [+0.1058, +0.5348] R)** |
| **NIFTY Buy-and-Hold** | +0.2373 R | [+0.1669, +0.3068] R | +0.0630 R (CI: [-0.1709, +0.2842] R, spans zero) |

---

## 4. Live Shadow Mode Status

- **Status:** **ACTIVE & OPERATIONAL** (`reports/shadow_mode_status.json`)
- **Execution Mode:** Pre-market screening cycle executed daily at 09:00 IST.
- **Order Routing:** **DISABLED** — Decision support only, zero broker orders placed.
- **Pick Logging:** Every candidate evaluated is stamped with cryptographic hash-chaining, recorded with `source="SHADOW"` and `is_shadow=True`.
- **"No Trade Today" Verification:** In adverse or unconfirmed technical setups, the system halts with `approved_count: 0`, enforcing discipline without forcing trades.
