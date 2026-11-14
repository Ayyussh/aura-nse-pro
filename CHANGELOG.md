# AURA-NSE Pro — Changelog

All notable changes to the AURA-NSE Pro platform are documented in this file.

## [2.0.0] - 2026-11-14

### Added
- **Promoter Group Caps (`config/groups.yaml`):** Mapped major Indian corporate conglomerates (Tata, Adani, Bajaj, ICICI, PSU, Birla, Murugappa, Reliance). Implemented `SKIPPED_GROUP_CAP` constraint in `backend/risk/sizing.py` enforcing max 2 open swing positions and max 25% total capital exposure per promoter group.
- **Milestone U0 Freeze & Audit:** Created `docs/AUDIT.md` mapping all items from Sections 18.2 to 18.5 with file and line references, severity, and compliance status. Created frozen baseline record in `reports/baseline_v0.json` with configuration hash, model metadata, and baseline backtest metrics.
- **Grader Dual R Outputs (`backend/core/grader.py`):** Grader now returns both `gross_pnl_r` and `net_pnl_r` to expose the exact statutory and exchange cost drag on trade outcomes.
- **ATR-Relative Anti-Chase Gate (`backend/core/pipeline.py`):** Replaced flat gap limit with an ATR-adaptive threshold: `clamp(0.5 * (ATR14 / planned) * 100, 0.75%, 2.5%)`. Openings through the stop loss trigger `SKIPPED_GAP_DOWN`, with whole-share quantity dynamically recomputed at market open.
- **REST API Upgrades (`backend/api/endpoints.py`):**
  - Added `POST /api/scanner/run` with job lock, idempotency support, and progress payload.
  - Added deprecated `GET /api/scanner/run` alias returning HTTP 405 Method Not Allowed with deprecation notice.
  - Added `GET /api/predictions/verify-chain` to programmatically verify cryptographic SHA-256 audit hash integrity across all stored predictions.
- **Universe Expansion (`backend/data/universe.py`):** Expanded active tracking universe to 191 high-liquidity equities, incorporating all Tata, Adani, ICICI, Bajaj, PSU, FMCG, and high-quality market duopolies.
- **Comprehensive Unit Tests (`tests/test_v2_upgrades_section18.py`):** Added 4 dedicated unit and integration tests verifying baseline freeze, dual R grader metrics, promoter group caps, and scanner API endpoints (26/26 tests passing).

### Changed
- `backend/core/config.py`: Integrated `get_groups_config()` and included `groups.yaml` inside the deterministic SHA-256 configuration hash calculation.
- `backend/risk/sizing.py`: Added promoter group exposure checks before position sizing.
