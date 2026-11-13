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
