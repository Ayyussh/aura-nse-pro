# AURA-NSE Pro: GitHub Actions Automation & Self-Improving Setup Guide

This guide details how to deploy **AURA-NSE Pro** to GitHub Actions for **24x7 autonomous operation**, uninterrupted CI/CD validation, and self-improving machine learning.

---

## 1. Architecture of Autonomous Automation

GitHub Actions acts as an institutional cloud scheduler with zero hosting costs:

```
[Monday - Friday Schedule (Asia/Kolkata)]
09:00 AM IST (03:30 UTC)  --> Pre-Market Screener, Regime Filter, ML Scoring, AURA LLM Audit, Telegram Alert
09:15 AM IST (03:45 UTC)  --> Market Open Anti-Chase Verification (Execute or Skip Gap-ups)
15:45 PM IST (10:15 UTC)  --> Post-Market Trade Grading, P&L, Statutory Charges & Mistake Logging
18:30 PM IST (13:00 UTC)  --> Official NSE UDiFF Bhavcopy EOD Reconciliation

[Saturday Schedule]
10:00 AM IST (04:30 UTC)  --> Mistake Lab Audit & Self-Improving ML Retraining / Model Promotion Loop
```

---

## 2. Step 1: Create GitHub Repository & Push Code

In your terminal or PowerShell inside `c:\test\stock prediction`:

```bash
# 1. Stage all project files
git add .

# 2. Make initial commit
git commit -m "feat: complete AURA-NSE Pro v2 with GitHub Actions automation and self-improving ML"

# 3. Rename branch to main
git branch -M main

# 4. Link your remote GitHub repository (replace with your repo URL)
git remote add origin https://github.com/<your-username>/aura-nse-pro.git

# 5. Push to GitHub
git push -u origin main
```

---

## 3. Step 2: Configure Workflow Permissions in GitHub

Because GitHub Actions runs in an ephemeral container, it needs permission to save trade history, model weights, and mistake rules back into your repository:

1. Go to your repository on GitHub.
2. Click **Settings** $\to$ **Actions** $\to$ **General**.
3. Scroll down to **Workflow permissions**.
4. Select **"Read and write permissions"**.
5. Check **"Allow GitHub Actions to create and approve pull requests"**.
6. Click **Save**.

---

## 4. Step 3: Add Encrypted Repository Secrets

Navigate to **Settings** $\to$ **Secrets and variables** $\to$ **Actions** $\to$ **New repository secret**:

| Secret Name | Description | Required? |
| :--- | :--- | :--- |
| `GEMINI_API_KEY_1` | Primary Google Gemini API key for AURA AI Analyst | **Yes** |
| `GEMINI_API_KEY_2` | Secondary Gemini API key for automatic 429 rotation | Optional |
| `TELEGRAM_BOT_TOKEN` | Bot token from `@BotFather` for morning signals | Recommended |
| `TELEGRAM_CHAT_ID` | Your private chat ID from `@userinfobot` | Recommended |
| `UPSTOX_ANALYTICS_TOKEN` | 1-Year Upstox Analytics Token for Tier-2 market data | Recommended |
| `APP_SECRET_KEY` | 32-byte Fernet key for encrypting secrets | Recommended |
| `HEALTHCHECKS_IO_URL` | Healthchecks.io ping URL for dead-man's switch alerts | Optional |

---

## 5. Step 4: Continuous Testing & Validation (CI/CD)

Every time you commit code or submit a pull request, the workflow `.github/workflows/ci.yml` triggers automatically:
- Executes Python 3.11 test suite (all 19 institutional unit tests covering charges, taxes, corporate actions, run-gate, and self-improving ML).
- Runs the Upstox API connectivity smoke test.
- Verifies that the React 19 / TypeScript frontend compiles cleanly without errors.

---

## 6. How the Self-Improving Feedback Loop Works

Unlike static trading bots, AURA-NSE Pro continuously learns from real market outcomes:

1. **Trade Outcome Logging:**
   - Every trade resolution at 15:45 PM IST is evaluated against NSE prices.
   - Winning setups (`TARGET_HIT`) are labeled `1`.
   - Losing setups (`STOP_LOSS_HIT` or `TIME_LIMIT_EXIT`) are labeled `0` and recorded in `MistakeLog`.

2. **Saturday Experience Replay & Retraining (`backend/ml/retrain.py`):**
   - The engine loads historical feature priors + all newly accumulated closed trade records (weighted 2x).
   - Trains a candidate calibrated probability classifier.

3. **Champion vs. Candidate Gate:**
   - Candidate model must satisfy:
     - **Brier Score Calibration $\le 0.24$**
     - **ROC-AUC $\ge 0.58$**
     - **Brier Score must beat or equal the current Champion.**
   - If passed: The model is **PROMOTED** to Champion, serializing `champion_model.joblib` and bumping the model version (`v1.0.0` $\to$ `v1.1.0`).
   - If failed: Candidate is rejected, and Champion is retained.

4. **Dynamic LLM Failure Pattern Feedback:**
   - High-frequency mistake categories (e.g. *"False breakout on high VIX"*) are distilled into `data/mistake_rules.json`.
   - `aura_analyst` dynamically injects these exact rules into future Bull/Bear debates as negative few-shot constraints, preventing the LLM from repeating recent errors.

5. **Automatic State Persistence:**
   - The GitHub Actions workflow automatically commits updated `backend/aura_nse.db`, `backend/ml/models/`, and `data/mistake_rules.json` back to your repo using `[skip ci]`.

---

## 7. Manual Testing (One-Click Trigger)

You do not have to wait for 9:00 AM IST to test:

1. On GitHub, navigate to the **Actions** tab.
2. Select **"AURA Market Automation & Self-Improving Pipeline"**.
3. Click **Run workflow**:
   - Choose phase: `full_cycle`, `premarket`, `open_check`, `postmarket`, or `retrain`.
   - Check `force: true` if testing on a weekend or holiday.
4. Watch the live console logs as AURA screens stocks, scores probabilities, audits setups, and commits the updated ledger.
