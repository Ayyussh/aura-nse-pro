# AURA-NSE Pro Build & Operations Makefile

.PHONY: help dev test seed backtest build lint clean verify

help:
	@echo "AURA-NSE Pro — Investor-Grade Indian Equities Decision Support"
	@echo "------------------------------------------------------------"
	@echo "make dev       - Run FastAPI backend and Vite frontend concurrently"
	@echo "make test      - Run full pytest suite across all milestones"
	@echo "make seed      - Initialize database tables and seed default vault entries"
	@echo "make backtest  - Execute walk-forward stress test simulation"
	@echo "make build     - Build production React frontend bundle"
	@echo "make lint      - Check code quality with ruff / python syntax"
	@echo "make verify    - Full institutional verification suite (Section 19.9 & P8)"


dev:
	.venv\Scripts\python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

test:
	.venv\Scripts\pytest -v

seed:
	.venv\Scripts\python -m backend.db.init_db

backtest:
	.venv\Scripts\python -c "from backend.core.pipeline import run_pre_market_pipeline; print(run_pre_market_pipeline())"

build:
	cd frontend && npm run build

clean:
	rm -rf data/cache/*.parquet backend/ml/models/*.pkl

verify:
	powershell -ExecutionPolicy Bypass -File scripts/verify.ps1

