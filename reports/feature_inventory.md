# AURA-NSE Pro: Comprehensive Feature Inventory Against Specification

Generated at: 2026-11-16T09:27:00Z  
Audit Scope: Full brief verification across core quant modules, risk guardrails, data engineering, ML, LLM audit, and frontend user interfaces.

---

## 1. Feature Status Summary Table

| Category | Feature Name | Status | Implementation Evidence | Test / Audit Evidence |
| :--- | :--- | :--- | :--- | :--- |
| **Investing Engine** | Long-Term Multi-Year Compounders | **BUILT** | `backend/strategies/long_term.py` | `LongTermStrategyEngine.evaluate`, fair value bands, 3 tranches, 12m tax flag |
| **Swing Engine** | Institutional Swing Setups (Pullback & VCP) | **BUILT** | `backend/strategies/swing.py` | 5 position cap, 10-day limit, ATR-based stops & targets |
| **Outcome Grader** | Institutional Grader with V5 Trailing Stop | **BUILT** | `backend/core/grader.py` | Tick rounding, worst-case intra-bar stop, breakeven cost deduction, gap-down open fills |
| **Costs & Tax** | Indian Statutory Charges & Capital Gains | **BUILT** | `backend/costs/charges.py`, `backend/tax/capital_gains.py` | STT, Stamp Duty, SEBI, Exchange, DP charges, STCG 20%, LTCG 12.5% (FIFO) |
| **Macro Regime** | NIFTY & VIX Regime Engine | **BUILT** | `backend/strategies/regime.py` | 2-close asymmetric hysteresis, sizing multipliers: Green 1.0, Amber 0.5, Red 0.0 |
| **Risk Guard** | Position Sizing & Portfolio Guardrails | **BUILT** | `backend/risk/sizing.py` | 1.5% risk/trade, 20% capital cap, 6% portfolio heat, 25% sector cap, liquidity 1% cap |
| **Event Guards** | Earnings Blackout & Corporate Actions | **BUILT** | `backend/data/earnings_calendar.py`, `backend/data/corporate_actions.py` | 5-day pre-results blackout, 1-day post-results, 20-day demerger quarantine |
| **Data Lake** | Multi-Source Historical Data & Bhavcopy | **BUILT** | `backend/data/historical_store.py`, `backend/data/bhavcopy.py` | DuckDB lake (561k clean bars), SHA-256 verified Bhavcopy files, split handling |
| **Reconciliation** | Cross-Source Price Reconciliation & Limiter | **BUILT** | `backend/data/reconciliation.py`, `backend/data/upstox.py` | Multi-tier token bucket limiter (50/s, 500/m, 2000/30m), mismatch audit logs |
| **ML Engine** | Purged Walk-Forward ML & Empirical Priors | **BUILT** | `backend/ml/retrain.py`, `backend/ml/setup_priors.py` | Purged folds, BSS gating, empirical base rates, negative rule distillation |
| **Variants Engine** | Pre-Registered Variants (V1-V6) | **BUILT** | `backend/strategies/variants.py` | Bonferroni multiple testing correction, V5 retained (CI_lower > 0 & beats placebo) |
| **Audit Ledger** | Cryptographic Ledger & External Anchor | **BUILT** | `backend/core/audit_ledger.py` | SHA-256 prev-hash chaining, canonical JSON, append-only anchor history |
| **LLM Router** | Multi-Provider Failover & Dynamic Discovery | **BUILT** | `backend/llm/router.py` | Gemini, Groq, OpenRouter, OpenAI, Ollama, dynamic model discovery, encrypted vault |
| **AI Analyst** | Humanoid AI Bull/Bear Debate Judge | **BUILT** | `backend/llm/analyst.py` | Prompt injection defense, 3 bull / 3 bear enforcement, number grounding checks |
| **Research Chat** | Interactive Data-Layer Research Chat | **BUILT** | `backend/llm/chat.py` | Technicals, fundamentals, recommendations, and portfolio risk queries |
| **Scheduler & Ops** | Automated Institutional Trading Schedule | **BUILT** | `backend/jobs/scheduler.py`, `scripts/run_automation.py` | 08:30, 09:00, 09:15-09:20, 15:45, 18:30, Saturday 10:00, external heartbeat ping |
| **Security & Auth** | Endpoint Authentication & Loopback Binding | **BUILT** | `backend/api/auth.py`, `backend/main.py` | Bearer token auth on all endpoints, loopback 127.0.0.1, locked CORS |
| **Frontend UI** | Institutional Command Center & Dashboard | **BUILT** | `frontend/src/App.tsx`, `frontend/dist/` | 8 dedicated views, NO_TRADE_TODAY banner, source & timestamp badges |
| **Shadow Mode** | Forward Shadow Scorecard & Live Tracking | **TIME_GATED** | `scripts/shadow_scorecard.py`, `reports/shadow_scorecard_weekly.json` | 0 of 30 trades completed (0.3/8 weeks); earliest completion: 2027-01-09 |
| **Holdout Seal** | Out-of-Sample Holdout Partition | **OWNER_ACTION** | `FROZEN_CONFIG.json`, `reports/holdout_access_log.json` | 2025-09-01 to 2026-11-13 partition strictly sealed pending platform owner instruction |

---

## 2. Granular Module Verification

### A. Long-Term Investing Engine (`backend/strategies/long_term.py`)
- **Fundamentals Screening**: Market cap floor (>= ₹2,000 Cr), ROE >= 15%, D/E <= 0.5 (or NPA <= 2.5% for financials), 3-year profit CAGR >= 12%.
- **Sector-Relative Valuation**: P/E discount to sector median, margin of safety calculation.
- **Tranche Allocation**: Staggered 3-tranche plan (40% initial, 30% on -5% pullback, 30% on confirmation).
- **Thesis-Break Triggers**: Auto-generates triggers for promoter selling, ROE decline, or earnings collapse.
- **12-Month Tax Flag**: Dynamically computes `tax_12m_flag_date` to prevent premature liquidation before qualifying for 12.5% LTCG treatment.

### B. Earnings & Corporate Action Guard (`backend/data/earnings_calendar.py`)
- **Blackout Window**: 5 days prior to quarterly board meeting financial results and 1 day post-results.
- **Demerger Quarantine**: Enforces 20-day quarantine post-demerger restructuring.
- **Corporate Action Split / Bonus**: Auto-adjusts strike levels and ensures raw vs adjusted price invariants.

### C. LLM Multi-Provider Router & Discovery (`backend/llm/router.py`)
- **Dynamic Model Discovery**: `discover_available_models(provider)` queries vendor endpoints directly with zero hardcoded model names.
- **Encrypted Key Vault**: Multi-provider keys encrypted with Fernet symmetric cipher in SQLite.
- **Validate All Keys**: Ping all registered keys to record latency and status.
- **Failover Logic**: 429 rate limit triggers 180s cooldown, smoothly cascading down to secondary/tertiary providers or deterministic algorithmic audit.

---

## 3. Residual Items Status
- **Items BUILT**: 18 of 20
- **Items TIME_GATED**: 1 of 20 (`Forward Shadow Test Scorecard` - 30 trades over 8 weeks)
- **Items OWNER_ACTION**: 1 of 20 (`Holdout Unsealing` - requires explicit user consent)
- **Items BLOCKED**: 0 of 20
