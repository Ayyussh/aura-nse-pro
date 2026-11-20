# AURA-NSE Pro — Institutional Market Analytics & Valuation Terminal

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-0052FF.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/Frontend-React_19_+_Vite-61DAFB.svg)](https://react.dev/)
[![Upstox API v3](https://img.shields.io/badge/Market_Feed-Upstox_API_v3-7928CA.svg)](https://upstox.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Timezone: Asia/Kolkata](https://img.shields.io/badge/Timezone-Asia%2FKolkata_(IST)-orange.svg)]()

> **Statutory Disclaimer:**
> Educational decision support and analytical research software for personal, single-user use on Indian equities (NSE primary, BSE secondary). This platform does not provide financial advice, solicitation, or automated order execution. Backtests, simulations, and historical valuations do not guarantee future returns.

---

## Overview

**AURA-NSE Pro** is a high-performance quantitative valuation, equity screening, and portfolio risk terminal engineered for the Indian equity market. It bridges institutional-grade fundamental valuation with systematic momentum screening, live broker telemetry, and automated statutory cost accounting.

```
┌────────────────────────────────────────────────────────────────────────┐
│                      Tiered Indian Market Feeds                        │
│   Upstox API v3 (Live Batch Quotes) + NSE Official Daily Bhavcopy      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Dual-Horizon Intelligence Engine                     │
│  • Long-Term Value & Moat Screener: Intrinsic Worth, Margin of Safety  │
│  • Tactical Momentum Engine: Volatility-Adjusted 10-Day Swing Alpha    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│            Multi-Agent Dialectical Debate & Cognitive Routing          │
│  • Agent Bull (Growth/Momentum) vs Agent Bear (Risk/Forensics)         │
│  • Chief Arbitrator (CIO) Adjudication using Deep-Think Cognitive LLM  │
│  • Tiered Model Routing: Quick-Think (Flash/70B) vs Deep-Think (Pro/R1)│
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               Enterprise React 19 Terminal & HTML Dossiers             │
│   Obsidian Dark UI, 3-Tranche Ladders & Standalone Research Dossiers   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Key Modules

### 1. Long-Term Value & Moat Screener (1 to 3+ Years)
* **Intrinsic Worth & Margin of Safety:** Calculates justified intrinsic valuation bands using sustainable earnings power, ROE durability, and sector-bounded justified multiples.
* **Cyclical Trap Protection:** Sector-specific valuation constraints prevent naive multiple extrapolation on cyclical commodities (Metals, Energy, Mining) and mature capital goods.
* **Financial Health Gating:** Institutional filters evaluate Return on Equity (ROE), conservative industrial leverage, and appropriately classified operational funding ratios for Banks and NBFCs.
* **Staggered 3-Tranche Execution:** Automatically computes risk-mitigated entry ladders (40% initial allocation, 30% on pullback, 30% on deep value support) to optimize cost basis.
* **AI Moat & Governance Audit:** Deliberates business moat durability, secular growth characteristics, and thesis invalidation triggers.

### 2. Tactical Swing Momentum Engine (10-Day Horizon)
* **Volatility-Adjusted Swing Setups:** Scans liquid NSE equities for high-probability momentum structures with positive risk-to-reward profiles.
* **Market Regime Awareness:** Dynamically adjusts exposure based on NIFTY index structure and India VIX volatility regimes.
* **Execution & Anti-Chase Verification:** Pre-market 9:00 AM screening followed by 9:15 AM gap checks to prevent chasing opening auction extensions.

### 3. Tiered Market Data & Rate-Limit Management
* **Upstox API v3 Live Feed:** Batch-quoted real-time broker pricing adhering to multi-tier sliding-window rate limiters.
* **Exchange Reconciliation:** Cross-references pricing with official end-of-day NSE Bhavcopy archives for authoritative settlement.
* **Persistent Caching:** High-speed local analytical caching ensures rapid scans with zero external API throttling.

### 4. Statutory Cost & Capital Gains Tracking
* **Pre-Trade Friction Accounting:** Accounts for all mandatory Indian statutory charges (STT, Stamp Duty, GST, Exchange turnover fees, and DP charges).
* **Capital Gains Tax Ledger:** Automated lot-based tax tracking for Short-Term (STCG) and Long-Term (LTCG) holding periods.

### 5. Multi-Agent Dialectical Debate Engine (Bull vs. Bear vs. CIO Arbitrator)
Inspired by institutional trading desk deliberation and multi-agent LLM reasoning frameworks (such as *TradingAgents*), AURA implements an adversarial dialectical debate before capital deployment:
* **Two-Phase Architecture:** Rather than wasting tokens running LLM agents across 750+ raw stocks, AURA uses high-throughput vectorized screening to filter 750–2,760 stocks down to high-conviction candidates in seconds. Only qualified candidates undergo multi-agent deliberation.
* **Agent Bull (Growth & Momentum):** Constructs aggressive data-driven expansion theses evaluating technical trend alignment (20/50/200 MAs), volume absorption, Mansfield Relative Strength vs NIFTY 50, and earnings catalysts.
* **Agent Bear (Risk Officer & Short-Side Forensics):** Stress-tests and attempts to invalidate the trade, attacking overhead resistance supply clusters, macro/sector drag, cyclical peak risks, and stop-loss vulnerability.
* **Chief Arbitrator (CIO):** Moderates multi-round cross-examinations using high-reasoning **Deep-Think** cognitive models. Renders final binding verdicts (`APPROVED`, `APPROVED_REDUCED_SIZE`, `REJECTED`), conviction scores (0–100%), sizing multipliers, and explicit invalidation criteria.
* **Deterministic Offline Fallbacks:** Zero reliance on live LLM APIs. If external models are rate-limited or offline, deterministic algorithmic rules referee the setup seamlessly.

### 6. Tiered Cognitive Model Routing (Quick-Think vs. Deep-Think)
Optimizes LLM intelligence, speed, and cost efficiency by routing tasks based on cognitive intensity:
* **Quick-Think Tier (`QUICK_THINK_MODEL`, default: `gemini-2.5-flash`):** Sub-second latency models for rapid pre-market screening, news filtering, and turn-by-turn analyst debate arguments.
* **Deep-Think Tier (`DEEP_THINK_MODEL`, default: `gemini-2.5-pro`):** Heavy cognitive reasoning models for chief arbitrator adjudication, multi-round synthesis, and comprehensive research dossier generation.
* **Multi-Provider Vault Rotation:** Transparent failover and rotation across Google Gemini, Groq (Llama-3.3-70B), OpenRouter, OpenAI, and local Ollama instances.

### 7. Interactive Single-Ticker CLI & Standalone HTML Research Dossiers
Run an on-demand, institutional deep-dive on any NSE scrip from your terminal:
```bash
# Analyze any NSE equity with default 2-round debate
python scripts/analyze_ticker.py --ticker TATAMOTORS.NS

# Run a 3-round debate and automatically open the generated dossier in your browser
python scripts/analyze_ticker.py --ticker RELIANCE.NS --rounds 3 --open
```
* **Publication-Grade HTML Research Dossier:** Generates an obsidian-styled, standalone HTML dossier saved to `reports/dossier_<TICKER>.html` featuring:
  * Live price telemetry, 52-week range, and macro regime metrics.
  * Calibrated ML win probability and friction-adjusted Expected Value ($EV_R$).
  * Intrinsic fair worth valuation with Margin of Safety percentage.
  * Full transcript of Agent Bull vs. Agent Bear dialectical rounds with Chief Arbitrator rulings.
  * Staggered 3-Tranche allocation ladder (40% initial, 30% pullback, 30% deep value).
  * Paisa-accurate statutory charges breakdown (STT, Stamp Duty, Exchange fees, SEBI, GST, DP fees, and slippage).

---

## Getting Started

### Prerequisites
* **Python 3.11+**
* **Node.js 18+ & npm**
* Upstox Developer Account *(Optional for live market feed)*
* Telegram Bot Token *(Optional for mobile signal dispatches)*

### Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/Ayyussh/aura-nse-pro.git
   cd aura-nse-pro
   ```

2. **Configure Environment:**
   Copy the example environment template and configure your credentials:
   ```bash
   cp .env.example .env
   ```
   Key variables:
   * `UPSTOX_ANALYTICS_TOKEN`: Your Upstox API v3 access token for live feeds.
   * `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: For secure private alerts.
   * `GEMINI_API_KEY_1`: For institutional AI qualitative audits.

3. **Launch the Platform:**
   On Windows, simply run the launcher:
   ```cmd
   .\start.bat
   ```
   The terminal will launch at `http://127.0.0.1:8000`.

---

## Autonomous 24x7 Routine

AURA-NSE Pro includes an automated GitHub Actions pipeline that executes scheduled market routines:
* **09:00 AM IST:** Pre-market quantitative scan and Telegram dispatch.
* **09:15 AM IST:** Market-open gap verification.
* **15:45 PM IST:** Post-market performance review and trade grading.
* **16:30 PM IST:** Daily Long-Term Value & Moat Screener sweep.
* **18:30 PM IST:** Official NSE Bhavcopy reconciliation.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
