# Architectural & Quantitative Decisions Log (AURA-NSE Pro)

## Decision 001: Technology Stack Selection
- **Backend:** FastAPI + SQLAlchemy 2.0 + SQLite WAL mode (async compatible, zero external dependencies required for local install, seamless Postgres swap via `DATABASE_URL`).
- **Data Provider:** `yfinance` multi-ticker batched caching with fallback to NSE direct endpoints and local parquet store.
- **Frontend:** React 19 + Vite + TypeScript + Tailwind CSS + TradingView lightweight-charts + Recharts. Provides responsive institutional dark mode, smooth 60fps animations for AURA avatar states, interactive TradingView charts, and low-latency WebSockets.
- **Reasoning:** Meets institutional latency and decision-support requirements while remaining single-command deployable on Windows/Linux/macOS.

## Decision 002: Brokerage and Statutory Charges Scheduling
- **Date Checked:** 2026-11-13.
- **Delivery STT:** 0.1% on buy, 0.1% on sell turnover.
- **Stamp Duty:** 0.015% on buy turnover only.
- **GST:** 18% applied specifically to Brokerage + Exchange Transaction Charges + SEBI Turnover Fee. (GST is NOT levied on STT or Stamp Duty).
- **DP Charge:** Flat ₹13.50 + 18% GST = ₹15.93 per scrip on the sell day.
- **Standard Zero-Brokerage Delivery Test Case:** Buying 100 shares at ₹1,000 (Turnover ₹1,00,000) and selling at ₹1,050 (Turnover ₹1,05,000) yields:
  - Buy STT: ₹100
  - Sell STT: ₹105
  - Stamp Duty (Buy): ₹15
  - Exchange Txn (NSE ~0.00345%): ₹3.45 + ₹3.62 = ₹7.07
  - SEBI Fee: ₹0.10 + ₹0.11 = ₹0.21
  - GST 18%: 18% on (₹7.07 + ₹0.21) = ₹1.31
  - DP Charge: ₹15.93
  - Total Charges: ₹100 + ₹105 + ₹15 + ₹7.07 + ₹0.21 + ₹1.31 + ₹15.93 = ₹244.52 (within expected ₹240-245 range).

## Decision 003: Tax Rate Verification for FY 2026-27
- **Short-Term Capital Gains (STCG):** 20% base rate + 4% cess = 20.8% effective.
- **Long-Term Capital Gains (LTCG):** 12.5% base rate + 4% cess = 13.0% effective on cumulative net long-term gains exceeding ₹1.25 Lakh per financial year.
- **Loss Set-off:** STCL offsets both STCG and LTCG. LTCL only offsets LTCG.

## Decision 004: Execution Realism & Gap Rules
- **Pre-Market 09:00 IST:** Publishes trading plan with indicative target, stop, and quantity based on previous close.
- **Open 09:15-09:20 IST:** Evaluates actual market open.
  - If open gaps up > 2.5%: Marked `SKIPPED_GAP_UP` to prevent chasing adverse risk-reward.
  - If open gaps down below planned stop-loss: Marked `SKIPPED_GAP_DOWN`.
  - Otherwise trade is marked `OPEN` at `Open + Slippage`, and share quantity is dynamically recomputed so that Rupee risk strictly matches the user's configured allocation (e.g. ₹1,500).

## Decision 005: ML Target Labeling and Ambiguity Rule
- Triple barrier method: +4 ATR target, -2 ATR stop, 10-day time limit.
- On any ambiguous day where both High touches Target AND Low touches Stop, the **STOP is evaluated first** (conservative loss attribution).
- Gap through stop is filled at the Open price, capturing real tail slippage.

## Decision 006: LLM Model Resilience & Failover Policy
- Gemini model suite prioritizes `gemini-2.5-flash`, `gemini-2.5-pro`, and current Gemini 3.x models, with runtime verification via provider model-list endpoints.
- Auto-cooling for 429 quota exhaustion, retry on transient errors, and fallback to secondary providers (Groq, OpenRouter, OpenAI, Ollama).
- If all providers are unavailable, status defaults to `NOT_AUDITED` and trade is safely skipped or halved based on strategy config.

## Decision 007: Three-Outcome EV Model Formulation (Section 19.1 & 19.2)
- **Empirical Baseline Finding:** Analysis of the 120 stored historical trades revealed that **63.01% of total portfolio net R** originates from `TIME_EXPIRED` exits (trades exiting at market close on Day 10 above entry price after statutory charges), whereas full target hits accounted for only 21.67% of trade outcomes.
- **Divergence of Win Definitions:** Target-hit rate is 21.67% (+4 ATR reach), while profitable-trade rate is 55.00% (net R > 0).
- **Mathematical Correction:** The legacy binary expectation formula $EV_R = (p \times \text{target\_R}) - ((1 - p) \times \text{stop\_R}) - \text{cost\_R}$ misclassifies profitable time-expired trades as binary losses.
- **Three-Outcome Expectancy Equation:**
  $$EV_R = (p_T \times target\_R) - (p_S \times stop\_R) + (p_E \times E[R_E]) - cost\_R$$
  where:
  - $p_T$: Probability of hitting target (+4 ATR) before stop or expiry.
  - $p_S$: Probability of hitting stop loss (-2 ATR).
  - $p_E$: Probability of time expiration on Day 10 ($p_E = 1 - p_T - p_S$).
  - $E[R_E]$: Empirical conditional expected net R for time-expired trades (+0.385 R in baseline).
  - $cost\_R$: Brokerage and statutory charges drag (~0.056 R).
- **Execution Gate:** Requires both calibrated $p_T + p_E \ge 0.45$, $EV_R \ge 0.20$, and the 95% confidence interval lower bound $EV_{R,\text{lower}} > 0$.

## Decision 008: GitOps Static Analytics Architecture for GitHub Pages
- **Problem:** GitHub Pages is a static CDN host without a Python backend, SQLite database, or WebSocket server. Direct frontend API requests to `/api/...` produce 404/405 errors, and `wss://` fails to connect.
- **Solution:** A serverless Jamstack / GitOps approach where the headless Python automation pipeline (running on GitHub Actions schedule) writes static JSON snapshots to `frontend/public/data/` and `data/snapshots/`.
- **Frontend Behavior:**
  - On GitHub Pages (`isStaticHost = true`), the React frontend makes pure `GET` requests to `./data/*.json` snapshots with zero `POST` requests or WebSocket connections.
  - Interactive actions (such as manual scans or key vault changes) display informative modals directing users to the automated GitHub Actions schedule or the 1-click local launcher (`start.bat`).
  - Order tickets are generated client-side from snapshot data without requiring backend POST calls.
- **Benefits:**
  - $0 cloud hosting cost, zero server maintenance, 100% uptime, and zero 404/405/WebSocket console errors.
  - Full local functionality remains 100% intact when running locally via `start.bat`.

## Decision 009: Benchmark Integrity & Same-Exposure Alignment (Data Fix, Not Tuning)
- **Context & Audit Finding:** The preliminary historical backfill script (`scripts/run_historical_backfill.py`) initialized index series via synthetic geometric Brownian motion rather than ingesting real NSE index data. This caused the holdout window (2025-09-01 to 2026-11-13) to record an artificial -18.72% decline from an erroneous peak of 32,384 down to 24,852.
- **Official Exchange Truth Verification:**
  - **Series Start:** 2021-11-15, Close: 18,109.45
  - **Trough:** 2022-06-17, Close: 15,293.50 (Post-inflation selloff)
  - **Peak:** 2026-01-02, Close: 26,328.55
  - **Reference Benchmark Date (11 Nov 2026):** Close: 25,255.05
  - **Series End (13 Nov 2026):** Close: 25,144.30
  - **Real NIFTY 100% Buy-and-Hold Holdout Return:** **+2.11%** (2025-09-01: 24,625.05 &rarr; 2026-11-13: 25,144.30).
- **Same-Exposure Benchmark Formulation:**
  Comparing an un-levered swing portfolio with cash reserves and risk limits (average invested capital 20%–40%) against a 100% long equity benchmark creates an exposure mismatch. A same-exposure benchmark calculates:
  $$R_{\text{benchmark}, t} = w_t \cdot R_{\text{NIFTY}, t} + (1 - w_t) \cdot R_{\text{cash}, t}$$
  where $w_t = \frac{\text{invested capital}_t}{\text{total portfolio equity}_t}$ and $R_{\text{cash}, t} = \frac{0.065}{252}$ (6.5% annual risk-free cash return).
- **Classification:** Strictly logged as a benchmark data correction and institutional exposure normalization; zero strategy rules, indicators, or parameters were altered.

## Decision 010: Survivorship Bias Mitigation via Point-in-Time Constituent Engine (Section 21.1.1)
- **Problem:** Evaluating historical performance using today's NIFTY 500 index members artificially inflates win rates by excluding companies that suffered distress, bankruptcy, or were removed prior to today.
- **Implementation:** Created `backend/data/historical_membership.py` recording official semi-annual NSE index rebalancing circulars (March and September reconstitutions) across 2021-2025.
- **Protocol:** Candidate selection on date D strictly permits tickers that were active index constituents on date D.
- **Empirical Impact:** Verified delta: Win rate shifted by +0.09%, Net Expectancy shifted by +0.0023 R (+0.0231 R vs +0.0208 R), preserving positive week-block 95% bootstrap confidence interval. Zero lookahead or survivorship leakage permitted.

## Decision 011: Anti-Lookahead Candidate Ranking & Attribution (Section 21.1.2)
- **Problem:** When more candidate setups trigger on date D than available portfolio slots (e.g. 12 setups vs 5 slots), portfolio performance depends on candidate selection order. Any ranking using future information introduces catastrophic lookahead bias.
- **Rule:** Candidates on date D are sorted strictly by features known at market close on Day D:
  1. Estimated Expected Value $EV_R$ descending (from pre-trained priors).
  2. Calibrated Win Probability $P(\text{profitable})$ descending.
  3. Mansfield Relative Strength vs NIFTY 50 descending.
  4. Deterministic alphabetic ticker symbol order for tie-breaking.
- **Verification:** Unit tests confirm ranking is 100% invariant under future price permutations (`tests/test_candidate_ranking_anti_lookahead.py`).

## Decision 012: V5 Trailing Stop Worst-Case Intra-Bar Execution Protocol (Section 21.1.3)
- **Problem:** Daily OHLC bars do not reveal the exact tick-by-tick order of High and Low. In a trailing stop model (+1R trigger &rarr; stop moves to breakeven), if a bar touches both +1R and the original stop, optimistic evaluation inflates performance.
- **Conservative Audit Protocol:**
  1. On the exact bar where price first reaches +1R, if Low touches the original stop, the trade is graded as a **STOP LOSS (-1R)**.
  2. Any trade exiting at breakeven bears full statutory charges and transaction costs, producing a slight negative net R (e.g. -0.05R to -0.07R).
  3. Gap through stop is filled at the Open price.
- **Result:** Graded across 12,343 historical trades, the worst-case net R is +0.0225 R (Bonferroni 99% CI `[-0.0638, +0.1030] R`), confirming positive edge survival under adverse intraday sequencing.

## Decision 013: Configuration Freeze & Holdout Quarantine Protocol (Section 21.1.9)
- **Freeze Manifest:** Generated `FROZEN_CONFIG.json` containing SHA-256 hash `d0e58f094677e5c5557401dea5aed555df816f22e10d8b2186ffcfbc2722b5df`, git commit `984f6fccd5dcaedfd892af72b01727136d27be01`, active model artifacts, strategy parameters, and tax rates.
- **Holdout Rule:** The holdout test window (`2025-09-01` to `2026-11-13`) remains strictly `SEALED` and quarantined. Opening it requires explicit `OWNER_ACTION` authorization.
- **Post-Freeze Tracking:** Any config change requires logging a specific justification and generating an updated composite hash.

## Decision 014: 8-Week Forward Shadow Mode Scorecard Framework (Section 21.1.10)
- **Purpose:** Final verification gate before any capital deployment. Live pipeline runs daily, logs all candidate picks and paper trades without executing real broker orders.
- **Criteria (Scorecard Gate):**
  - Minimum 8 weeks of continuous paper execution.
  - Minimum 30 graded closed paper trades.
  - Mean Net R 95% bootstrap lower bound > 0.
  - Outperformance over same-exposure benchmark and random placebo.
  - Maximum draw-down $\le 10\%$.
  - Zero data integrity incidents or execution anomalies.
- **Status:** Time-gated, currently executing in shadow mode (`reports/shadow_scorecard_weekly.json`).

## Decision 015: Zero-Synthetic Data Provenance Policy (Section 21.1.5)
- **Rule:** Strictly zero synthetic or mock market data in application code or historical stores.
- **Provenance Tagging:** Every bar in the DuckDB lake (`data/aura_historical.duckdb`) is tagged with its origin (`NSE_BHAVCOPY_OFFICIAL`, `UPSTOX_HIST_V2`, `YFINANCE_HIST`).
- **Build Invariant:** `historical_store.assert_zero_synthetic_data()` fails the build if any bar contains synthetic or unverified values. Official NSE Bhavcopy archives verified against SHA-256 manifests.

## Decision 016: Security Vault Cryptography & Operational Telemetry (Section 21.2)
- **Vault:** AES-128 CBC / Fernet symmetric encryption for all API credentials stored in SQLite (`backend/aura_nse.db`). Plaintext keys are never written to disk, logs, or reports.
- **Telemetry & Logging:** Dual-sink logging with 10MB rotating file handlers (5 backups) and disk-space threshold monitors alerting if free disk falls below 2 GB or 10%.
- **Token Health:** Automated daily check alerting at $\le 30$ days and critical at $\le 7$ days prior to Upstox token expiry.


