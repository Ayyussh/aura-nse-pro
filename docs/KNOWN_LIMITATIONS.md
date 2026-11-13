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
