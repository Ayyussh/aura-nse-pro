# AURA-NSE Pro — Investor-Grade Humanoid AI Indian Stock System & 30-Day Stress-Test Platform (v2.0)

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/Frontend-React_19_+_Vite-61DAFB.svg)](https://react.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Timezone: Asia/Kolkata](https://img.shields.io/badge/Timezone-Asia%2FKolkata_(IST)-orange.svg)]()

> **Statutory Compliance & Legal Disclaimer:**
> **Educational decision support, not investment advice. Backtests and paper results do not guarantee future returns.**
> This is a personal-use, single-user decision-support and paper-trading platform for Indian equities (NSE primary, BSE secondary). It generates trade plans exclusively for the owner's personal review and alerts are sent only to the owner's private Telegram chat/email. In India, distributing buy/sell recommendations to third parties or subscribers can require registration with SEBI as a Research Analyst (RA) or Investment Adviser (IA). SEBI maintains that using AI algorithms to generate calls does not diminish regulatory accountability. This application version 1 never places live exchange orders and never guarantees capital returns.

---

## 1. Executive Summary & Architecture

**AURA-NSE Pro** combines institutional quantitative screening, machine learning probability calibration, multi-LLM qualitative debate, an interactive Humanoid AI Analyst ("AURA"), realistic Indian tax and brokerage accounting, and an immutable 30-day walk-forward stress-test ledger.

```
                    ┌────────────────────────────────────────────────────────┐
                    │               NSE / BSE Live Market Feeds              │
                    │   yfinance OHLCV + Bhavcopy + India VIX + Indices      │
                    └───────────────────────────┬────────────────────────────┘
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 Backend Data & Quality Gate                                 │
│ - Price >= ₹50, 20d Volume >= 500,000, 20d Turnover >= ₹5 Cr, NIFTY 500 EQ-only            │
│ - Surveillance filter (exclude ASM/GSM/T2T), Outlier clamp, Parquet disk cache             │
└───────────────────────────────────────────────┬────────────────────────────────────────────┘
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                            Dual-Horizon Strategy & Regime Engine                           │
│ - Macro Regime: NIFTY 50 vs EMAs + India VIX -> Green (100%), Amber (50%), Red (0%)        │
│ - Swing Engine: Close > EMA50 > SMA200, ADX14 > 20, RSI 50-70, MACD, Volume > 1.2x, RS    │
│ - Long-Term Engine: Market Cap >= ₹2k Cr, ROE >= 15%, D/E <= 0.8, P/E <= 35, 3-Tranche     │
└───────────────────────────────────────────────┬────────────────────────────────────────────┘
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                             Machine Learning Probability Engine                            │
│ - LightGBM / Logistic Calibrated Classifier (Platt/Isotonic) on Triple Barrier Labels      │
│ - EV_R Gate: Require Win_Prob >= 45% and EV_R >= +0.20R (after Indian taxes & slippage)    │
│ - SHAP feature attribution & Brier score confidence calibration                            │
└───────────────────────────────────────────────┬────────────────────────────────────────────┘
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                         Multi-LLM Failover Vault & Bull/Bear Debate                        │
│ - Google Gemini (Primary: 2.5-flash, 2.5-pro, 3-flash) -> Groq -> OpenRouter -> Ollama    │
│ - Automatic 429 quota cooldowns, Fernet encryption at rest, live key latency tester        │
│ - AURA Humanoid Analyst: Bull vs Bear debate + red flag audit (pledge, governance)        │
└───────────────────────────────────────────────┬────────────────────────────────────────────┘
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                           Investor Risk Guard & Indian Charges                             │
│ - Position Sizing: Whole Qty = floor(Risk_INR / (Entry - Stop)), 20% max single stock cap   │
│ - Indian Charges: STT (0.1%), Stamp (0.015%), Exchange (0.00345%), SEBI, 18% GST, DP ₹16  │
│ - Tax Center (FY 26-27): STCG 20.8%, LTCG 13.0% over ₹1.25L, FIFO lots, set-off schedule   │
└───────────────────────────────────────────────┬────────────────────────────────────────────┘
                                                │
                                                ▼
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                           React 19 + Vite Dark Institutional UI                            │
│ - Interactive AURA Humanoid Avatar (Scanning, Analyzing, Bullish, Warning, Mistakes)       │
│ - Web Speech API Indian Voice Briefing (en-IN), captions, speech rate controls             │
│ - 30-Day Stress-Test Ledger, Equity Curve, R-Histogram, and Go-Live Readiness Scorecard    │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Investor Review & Critical Gap Analysis

*(Addressing: "act as an investor and check whether for an investor point of view what all is missing and what can we add in there")*

As an active institutional investor in Indian equities, deploying capital in the cash market involves real-world friction that typical retail backtests ignore. Here is the rigorous investor analysis:

### 1. Friction & Execution Reality (Gap vs. Plan)
- **Pre-Open Auction vs. 9:15 Continuous Trading:**
  Between 9:00 AM and 9:08 AM IST, the NSE pre-open auction determines equilibrium prices. High-beta swing stocks frequently gap up 1.5% to 3.0% due to overnight global cues (GIFT Nifty). If a trader buys at 9:15 AM after a 2.5% gap-up, their risk-reward ratio is decimated.
  - **AURA's Implementation:** Trades with gap-ups > 2.5% at 9:15 AM are strictly tagged `SKIPPED_GAP_UP` instead of chasing adverse pricing. Fills are executed at actual Open + slippage, and share quantity is dynamically recalculated to protect the exact ₹1,500 rupee risk budget.

### 2. High Statutory Cost Drag on Small Accounts
- In India, delivery trades incur **STT on both buy (0.1%) and sell (0.1%)**, Stamp Duty on buy (0.015%), Exchange transaction fees, SEBI fees, 18% GST, and a **flat DP charge (~₹15.93 per scrip sell day)**.
  - **The Mathematical Reality:** On a ₹1,00,000 account taking ₹20,000 positions, a round-trip costs ~₹244.52. If a trade makes ₹1,000 gross profit, 24.5% of the gain is wiped out by statutory fees before taxes!
  - **AURA's Implementation:** Every candidate passes through an **Expected Value Gate** ($EV_R = p \times 2.0 - (1-p) \times 1.0 - \text{cost}_R \ge 0.20R$). Candidates with gross 1:2 R:R that degrade below 1:1.8 net after Indian charges are rejected.

### 3. Promoter Pledging & Governance Traps
- The most catastrophic losses in Indian mid/small caps (e.g. historical cases like Zee, Cox & Kings, DHFL) originated from sudden promoter pledge invocation triggering relentless lower-circuit sell locks.
  - **AURA's Implementation:** The Long-Term engine enforces a hard cap of **Promoter Pledge $\le$ 10%** and audits whether promoter holding dropped $> 3$ percentage points over 4 quarters. The LLM Bull/Bear auditor specifically flags pending litigation, auditor resignations, and credit rating downgrades.

### 4. Post-Budget 2024 / FY 2026-27 Capital Gains Tax Architecture
- Under current tax laws:
  - **Short-Term Capital Gains (STCG):** 20% + 4% cess = **20.8%**.
  - **Long-Term Capital Gains (LTCG):** 12.5% + 4% cess = **13.0%** on gains above ₹1.25 Lakh per financial year (no indexation).
  - **AURA's Implementation:** Dual P&L reporting (Gross vs. Pre-tax Net vs. Post-tax Net), FIFO lot accounting, statutory set-off rules (STCL offsets STCG/LTCG, LTCL only offsets LTCG), and automated 12-month deferral alerts when holdings reach Day 330+.

### 5. What Was Added Beyond Standard Setups
- **Small-Sample Warning Banner:** Flags "INSUFFICIENT SAMPLE" when live forward paper trades are $< 30$.
- **Go-Live Readiness Scorecard:** Five-point institutional criteria checklist preventing premature deployment of real capital until statistically proven.
- **Ambiguous Bar Conservative Stop-First:** If a daily OHLC touches both Target and Stop, Stop is evaluated first.

---

## 3. Automation Timetable (Asia/Kolkata Timezone)

APScheduler executes the following persistent jobs:

| Time (IST) | Scheduled Task | Description |
|:---|:---|:---|
| **08:30 AM** | `0830_data_refresh` | Fetches GIFT Nifty cues, updates India VIX, computes Macro Regime (Green/Amber/Red) |
| **09:00 AM** | `0900_pre_market_plan` | Screens NIFTY 500, ML EV_R scoring, LLM Bull/Bear audit, publishes `OPEN` trade cards, generates spoken briefing & Telegram alert |
| **09:15 AM** | `0915_open_check` | Evaluates actual open prices: skips gap-ups > 2.5%, fills trades, recalculates whole quantity |
| **03:45 PM** | `1545_post_market_grading`| Grades open positions against daily High/Low/Close (`TARGET_HIT`, `STOP_LOSS_HIT`, `TIME_EXPIRED`) |
| **06:30 PM** | `1830_reconciliation` | Reconciles execution data against official NSE closing bhavcopy with immutable audit log |
| **Sat 10:00 AM**| `saturday_mistake_audit`| Analyzes loss clusters (`High VIX Trap`, `False Breakout`), proposes guardrail adjustments & retrains ML |

---

## 4. Quick Start & Installation

### Prerequisites
- Python 3.11+
- Node.js v18+ and npm
- (Optional) `uv` for 10x faster Python package installation

### 1. Clone & Setup Backend
```bash
git clone https://github.com/your-username/aura-nse-pro.git
cd aura-nse-pro

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

# Install backend dependencies
pip install -r requirements.txt
# (or with uv: uv pip install -r requirements.txt)

# Initialize SQLite database and tables
python -m backend.db.init_db
```

### 2. Configure Environment (`.env`)
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```
Key configuration parameters:
```ini
APP_ENV=development
APP_SECRET_KEY=aura_super_secret_master_key_change_in_production_32b_hex
FERNET_ENCRYPTION_KEY=foanu4O2YDcNm1fdb0wf4QhriLAudEsrpnhrsBARTCc=
DATABASE_URL=sqlite:///./backend/aura_nse.db
TIMEZONE=Asia/Kolkata

# LLM Vault (Google Gemini primary)
GEMINI_API_KEY_1=your_gemini_key_here
GEMINI_API_KEY_2=your_fallback_gemini_key
GROQ_API_KEY=your_groq_key

# Telegram Notifications (Private Chat)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 3. Build & Run Frontend
```bash
cd frontend
npm install
npm run build
cd ..
```

### 4. Launch Application
```bash
# Start FastAPI backend (serves built React frontend on http://localhost:8000)
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
Open your browser at **`http://localhost:8000`** to access the AURA-NSE Pro Institutional Dashboard.

---

## 5. Verification & Test Suite

The system includes comprehensive automated unit tests covering all mathematical, risk, tax, and failover requirements:

```bash
pytest -v
```

### Verified Test Cases:
1. `test_charges_worked_example`: Buying 100 shares at ₹1,000 and selling at ₹1,050 yields **₹244.52 in total charges** (matching the ₹240-245 requirement).
2. `test_tax_engine_fifo_and_setoff`: Validates FIFO lot tracking, ₹1.25L LTCG exemption, and statutory loss set-offs.
3. `test_position_sizing_and_regime`: Verifies whole-share quantity truncation, AMBER 50% halving, RED zero-entry blocking, and the 20% single position capital cap.
4. `test_grader_stop_first_on_ambiguous_bar`: Confirms conservative stop-first outcome attribution when both Target and Stop are touched on the same day.
5. `test_grader_gap_down_through_stop`: Validates that gap-down exits fill at Open, capturing real tail slippage.
6. `test_ml_leakage_and_ev_gate`: Confirms shuffled labels produce ~50% AUC (no data leakage) and verifies EV_R gates.
7. `test_llm_rotation_on_simulated_429_and_failover`: Simulates 429 quota exhaustion and verifies automatic cooldown and failover to secondary keys.

---

## 6. Directory Layout

```
├── backend/
│   ├── api/
│   │   ├── auth.py              # Single-user authentication & session management
│   │   └── endpoints.py         # Full REST API routes (regime, predictions, vault, etc.)
│   ├── core/
│   │   ├── backtest.py          # 30-day forward & multi-year walk-forward stress test
│   │   ├── config.py            # Pydantic settings & Fernet encryption
│   │   ├── grader.py            # Tick-aware rounding, tie-breaker & trade outcome grader
│   │   └── pipeline.py          # 9:00 AM scan, 9:15 AM open check, 15:45 PM grading
│   ├── costs/
│   │   └── charges.py           # Indian statutory charges engine (STT, Stamp, Txn, GST, DP)
│   ├── data/
│   │   ├── bhavcopy.py          # Official NSE UDiFF CM Bhavcopy parser & parquet cache
│   │   ├── contract_note.py     # Broker tradebook CSV reconciliation & charge drift
│   │   ├── corporate_actions.py # Corporate action ledger, jump detector & demerger policy
│   │   ├── holiday_calendar.py  # Official NSE trading holidays & special sessions
│   │   ├── provider.py          # yfinance provider, parquet caching, quality gate, news
│   │   ├── reconciliation.py    # Multi-source price truth (Grades A/B/C) & 98% run gate
│   │   ├── universe.py          # NIFTY 500 equity universe & sector mappings
│   │   └── upstox.py            # Upstox API v3 client with 1-Year Analytics Token
│   ├── db/
│   │   ├── init_db.py           # Database initializer & table creation
│   │   ├── models.py            # SQLAlchemy models (Prediction, Trade, Vault, Mistake)
│   │   └── session.py           # SQLite in WAL mode with connection pooling
│   ├── jobs/
│   │   └── scheduler.py         # Persistent APScheduler in Asia/Kolkata timezone
│   ├── llm/
│   │   ├── analyst.py           # AURA Humanoid Analyst (Bull, Bear & Judge stages)
│   │   ├── chat.py              # Interactive research console with tool calling
│   │   └── router.py            # Multi-LLM failover router (Gemini, Groq, OpenRouter)
│   ├── ml/
│   │   ├── features.py          # Point-in-time quantitative features & triple-barrier
│   │   ├── predictor.py         # Calibrated classifier, EV_R gate, SHAP attributions
│   │   └── retrain.py           # Self-improving feedback loop, champion vs candidate gate
│   ├── risk/
│   │   └── sizing.py            # Whole-share position sizing, 20% cap, drawdown breakers
│   ├── strategies/
│   │   ├── indicators.py        # Vectorized EMA, ATR, RSI, MACD, ADX calculations
│   │   ├── long_term.py         # Multi-year institutional compounder engine
│   │   ├── regime.py            # NSE Macro Regime & sector momentum scoring
│   │   └── swing.py             # 5-15 day swing engine (Close > EMA50 > SMA200, 1:2 R:R)
│   ├── tax/
│   │   └── capital_gains.py     # Indian Capital Gains engine (FY 26-27: STCG 20.8%, LTCG 13.0%)
│   └── main.py                  # FastAPI app, static build server & WebSockets
├── config/
│   ├── charges.yaml             # Versioned Indian statutory charge schedule
│   ├── strategy.yaml            # Strategy thresholds, risk rules, and readiness targets
│   └── tax.yaml                 # Capital gains rates, exemption limits, and set-offs
├── docs/
│   ├── DECISIONS.md             # Architecture & quantitative decision records
│   ├── GITHUB_ACTIONS_SETUP.md  # 24x7 autonomous automation & GitHub Secrets guide
│   └── KNOWN_LIMITATIONS.md     # Production operational boundaries & rate limits
├── frontend/                    # React 19 + Vite + TypeScript institutional dark UI
├── scripts/
│   ├── run_automation.py        # Headless automation CLI for GitHub Actions & schedulers
│   └── upstox_smoke_test.py     # Tier-2 Upstox API connectivity test
├── tests/                       # Complete 19-test pytest suite
└── requirements.txt             # Pinned dependencies
```

---

## 7. Autonomous 24x7 Execution & Self-Improving Feedback Loop

See [docs/GITHUB_ACTIONS_SETUP.md](file:///c:/test/stock%20prediction/docs/GITHUB_ACTIONS_SETUP.md) for full deployment instructions.

1. **GitHub Actions 24x7 Scheduler:**
   - Runs uninterrupted on the official NSE schedule (`09:00 IST`, `09:15 IST`, `15:45 IST`, `18:30 IST`, and Saturday `10:00 IST`).
   - Automatically commits trade logs, SQLite database, and model updates back to your repository using `[skip ci]`.
2. **Self-Improving Machine Learning:**
   - **Closed Feedback Loop:** Graded live trade outcomes (`TARGET_HIT` vs `STOP_LOSS_HIT`) are fed into `backend/ml/retrain.py`.
   - **Champion vs Candidate Gate:** Retrained models must pass Brier Score ($\le 0.24$) and ROC-AUC ($\ge 0.58$) gates to be promoted.
   - **Dynamic LLM Failure Patterns:** High-frequency loss categories are extracted into `data/mistake_rules.json` and injected into AURA's LLM prompt, actively preventing the AI from repeating past errors.

---

## 8. License & Compliance
This software is provided under the MIT License for educational research and personal decision support.
