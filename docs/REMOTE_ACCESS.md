# Remote Access Architecture & Offline Resilience (AURA-NSE Pro)

This document describes how to securely access the AURA-NSE Pro dashboard remotely (e.g. from mobile or laptop while away from home) without compromising security or exposing unauthenticated ports to the public internet, and documents system resilience during internet outages.

---

## 1. Security Baseline & Threat Model

By default, AURA-NSE Pro binds strictly to the loopback interface:
- **FastAPI Backend:** `http://127.0.0.1:8000`
- **React UI Development / Preview:** `http://127.0.0.1:5173` or `http://127.0.0.1:4173`
- **CORS Policy:** Restricted to `http://localhost:5173`, `http://127.0.0.1:5173`, and authorized local loopback origins.

> [!CAUTION]
> Never bind the server directly to `0.0.0.0` or open port 8000 on your residential router. Doing so exposes your internal database, decrypted trading keys, and financial analytics to public internet port scanners.

---

## 2. Secure Remote Access Options

### Option A: Tailscale Mesh VPN (Recommended)

Tailscale provides an encrypted, peer-to-peer WireGuard mesh network connecting your host PC, smartphone, and laptop with zero open firewall ports.

#### Setup Steps:
1. **Install Tailscale on Host PC (Windows):**
   - Download and install Tailscale from [tailscale.com](https://tailscale.com/).
   - Sign in with your personal account (Google/Microsoft/GitHub).
   - Note your PC's MagicDNS name or Tailscale IP (e.g., `100.x.y.z` or `aurapc.ts.net`).
2. **Install Tailscale on Mobile / Remote Laptop:**
   - Install the Tailscale app from iOS App Store or Google Play Store.
   - Sign in with the identical account.
3. **Configure AURA Host for Tailscale Access:**
   - In `backend/main.py` or startup arguments, bind to your Tailscale IP or allow the Tailscale interface:
     ```powershell
     # Launch binding to localhost and Tailscale IP
     uvicorn backend.main:app --host 0.0.0.0 --port 8000
     ```
   - *Security Guard:* Ensure Windows Defender Firewall is set to block inbound connections from Public networks while allowing connections only on the `Tailscale` network adapter.
4. **Access the Dashboard:**
   - From your smartphone browser, navigate to `http://100.x.y.z:8000` or `http://aurapc.ts.net:8000`.

---

### Option B: Cloudflare Zero Trust Tunnel

Cloudflare Tunnel (`cloudflared`) connects your local application securely to Cloudflare's edge without opening inbound router ports. You can enforce Google OAuth or Email One-Time Pin (OTP) before granting access.

#### Setup Steps:
1. **Install cloudflared:**
   - Download `cloudflared.exe` from Cloudflare Zero Trust dashboard.
2. **Authenticate & Create Tunnel:**
   ```powershell
   cloudflared tunnel login
   cloudflared tunnel create aura-tunnel
   ```
3. **Configure Tunnel (`config.yml`):**
   ```yaml
   tunnel: <TUNNEL_UUID>
   credentials-file: C:\Users\PC\.cloudflared\<TUNNEL_UUID>.json

   ingress:
     - hostname: aura.yourdomain.com
       service: http://127.0.0.1:8000
     - service: http_status:404
   ```
4. **Enforce Cloudflare Access Policy:**
   - In Cloudflare Zero Trust dashboard, navigate to **Access > Applications**.
   - Add `aura.yourdomain.com` with an **Allow** policy restricted exclusively to your own verified email address.
5. **Start Tunnel:**
   ```powershell
   cloudflared tunnel run aura-tunnel
   ```

---

## 3. Offline Resilience & Degraded Network Modes

AURA-NSE Pro is designed to maintain core decision-support functionality even during ISP outages, broker API rate limits, or upstream downtime:

### 1. Data Store Cache Priority
- Price data is queried with a local-first policy:
  1. Local DuckDB analytical store (`data/aura_historical.duckdb`).
  2. Local SQLite cache (`backend/aura_nse.db`).
  3. External network fetch (NSE Bhavcopy / Upstox / yfinance).
- If internet connectivity is completely lost, the system computes technical indicators, setup scans, and position sizing using the most recent cached market bar and displays a persistent `STALE_DATA_BADGE (Offline)` indicator.

### 2. Local LLM Fallback (Ollama)
- When cloud LLM endpoints (Gemini, Groq, OpenRouter) fail due to network timeouts:
  - If a local Ollama instance is running (`http://localhost:11434`), qualitative debate queries automatically fail over to `ollama/deepseek-r1` or `ollama/llama3.3`.
  - If no local LLM is running, trade plans are safely marked `NOT_AUDITED`. The system continues to generate quantitative signals with conservative risk sizing.

### 3. Voice Briefing Offline Synthesis
- AURA's voice briefings use browser-native Web Speech API (`window.speechSynthesis`), which executes 100% locally on your browser without making third-party cloud API calls.
- Full transcript text is saved to SQLite, ensuring the briefing is readable even if browser audio permissions are blocked.

### 4. Alert Queueing
- If Telegram alert dispatch fails due to an ISP outage, failed alerts are stored in the `alert_logs` table with status `FAILED_NETWORK_RETRY`.
- Upon network restoration, the next scheduled heartbeat task flushes the queued notifications.
