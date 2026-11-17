# Known Limitations & Operating Boundaries (AURA-NSE Pro)

## 1. Unofficial Data Provider & Rate Limits
- `yfinance` is an unofficial interface to public financial data. While AURA-NSE Pro incorporates multi-threaded batched fetches, parquet disk caching, and retry with exponential backoff, rate limits can occur during high-frequency scans.
- Fallback mechanisms connect to NSE bhavcopy downloads and allow pluggable broker feeds (Zerodha Kite, Upstox, Dhan).

## 2. Fundamentals Data Freshness for Indian Equities
- Fundamentals (ROE, ROCE, P/E, Debt-to-Equity, Promoter Pledge) fetched from free public web scrapers can experience a 1-to-2 week lag post quarterly earnings announcements.
- AURA-NSE Pro marks unverified fields as `UNKNOWN` rather than passing them silently, and includes a 1-click Screener.in CSV importer to guarantee 100% audited institutional fundamentals.

## 3. Web Speech API Browser Autoplay Restrictions
- Modern web browsers (Chrome, Firefox, Safari, Edge) enforce strict security policies blocking unsolicited audio autoplay.
- AURA's voice briefing requires an initial user interaction (e.g. clicking "Play Morning Briefing" or unmuting the avatar) before synthesizing audio speech. Full visual captions and transcript cards are always provided.

## 4. Single-User Decision Support Scope
- AURA-NSE Pro is strictly an educational decision-support and paper-trading platform. It does not execute live orders on exchange order books and does not broadcast recommendations to third-party channels.
- Backtests and paper-trading metrics do not account for instantaneous market impact of multi-crore institutional blocks.

## 5. Daily Bar Intraday Path Ambiguity
- Daily OHLCV bars do not provide intra-bar tick sequences. On days where both high and low breach critical price boundaries (+1R trigger and original stop), the system enforces a strict worst-case order assumption (stop loss hit first, -1R attribution).
- For live shadow execution, intraday tick logging or trailing stop orders placed directly at the broker would provide precise tick execution.

## 6. Corporate Action & Restructuring Quarantines
- Stock splits and bonus issues are automatically adjusted across price and quantity histories.
- However, complex demergers (e.g. spinoffs like Tata Motors PV/CV, Vedanta) disrupt technical indicators (EMA, ATR) and ML feature baselines. Any stock undergoing a major demerger is placed under a strict 20-trading-day quarantine during which trading signals are suppressed.

## 7. Dual Operating Modes: GitOps Static Host vs Local Full-Stack
- On GitHub Pages (`isStaticHost = true`), the platform operates as a read-only analytics portal consuming pre-generated JSON snapshots. Live WebSockets and interactive POST endpoints are inactive.
- Full interactive capabilities (real-time scans, encrypted vault management, instant ML retraining) run via local backend server (`start.bat`).

## 8. Forward Shadow Scorecard Time-Gate
- Historical edge validation (survivorship-corrected, Bonferroni-corrected, placebo-beating) is necessary but insufficient for capital allocation.
- The system enforces a mandatory 8-week, 30-trade forward live paper trading period before any go-live recommendation can be issued.

