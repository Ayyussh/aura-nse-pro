"""AURA-NSE Pro Automated Dashboard Screenshot Capture (Section 21.2 Item 2).

Captures full-page screenshots of all 8 primary application views:
1. AURA Command Center (avatar, voice, captions, NO_TRADE_TODAY banner)
2. Stress Test and Net P&L (equity curves, daily drawdown, Monte Carlo)
3. Portfolio and Risk Guard (active positions, sector heat, caps)
4. Mistake Lab (dynamic negative rule distillation, proposal approval flow)
5. Key, Model and Alert Vault (multi-LLM keys, rate limit gauges, Telegram alerts)
6. Research and Watchlist (data-grounded interactive research console)
7. Journal and Tax Center (charges breakdown, STCG/LTCG tax estimates, FIFO)
8. System Health (memory, DuckDB bar count, rate limiter status, cron schedules)

Output directory: reports/screenshots/
"""

from __future__ import annotations
import os
import sys
import time
import socket
import threading
import http.server
import socketserver
from pathlib import Path
from playwright.sync_api import sync_playwright

_project_root = Path(__file__).resolve().parent.parent
DIST_DIR = _project_root / "frontend" / "dist"
SCREENSHOTS_DIR = _project_root / "reports" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class CustomHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "application/javascript",
        ".mjs": "application/javascript",
        ".css": "text/css",
        ".json": "application/json",
        ".wasm": "application/wasm",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)

    def log_message(self, format, *args):
        pass  # Suppress server logs


def run_server(port: int):
    with socketserver.TCPServer(("", port), CustomHandler) as httpd:
        httpd.serve_forever()


def capture_all_views():
    if not (DIST_DIR / "index.html").exists():
        raise FileNotFoundError(f"Frontend dist not found at {DIST_DIR}. Run 'npm run build --prefix frontend' first.")

    port = find_free_port()
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()
    time.sleep(1.0)

    url = f"http://127.0.0.1:{port}"
    print(f"Preview server started on {url}")

    views = [
        {"tab_name": "Command Center", "file_name": "01_command_center.png"},
        {"tab_name": "30-Day Stress Test", "file_name": "02_stress_test.png"},
        {"tab_name": "Risk & Portfolio", "file_name": "03_portfolio_guard.png"},
        {"tab_name": "Mistake Lab", "file_name": "04_mistake_lab.png"},
        {"tab_name": "Key Vault", "file_name": "05_key_model_vault.png"},
        {"tab_name": "AI Research", "file_name": "06_research_console.png"},
        {"tab_name": "Tax & Charges", "file_name": "07_journal_tax_center.png"},
        {"tab_name": "System Health", "file_name": "08_system_health.png"},
    ]

    captured_files = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        page.goto(url, wait_until="networkidle")
        time.sleep(1.5)

        for view in views:
            tab_text = view["tab_name"]
            out_file = SCREENSHOTS_DIR / view["file_name"]

            # Click tab button
            button = page.get_by_role("button", name=tab_text, exact=False).first
            if button.is_visible():
                button.click()
                time.sleep(1.0)
            else:
                print(f"Warning: Button for '{tab_text}' not visible directly, checking text selector...")
                page.locator(f"button:has-text('{tab_text}')").first.click()
                time.sleep(1.0)

            # Capture full page screenshot
            page.screenshot(path=str(out_file), full_page=True)
            size_kb = round(out_file.stat().st_size / 1024, 1)
            print(f"Captured {view['file_name']} ({tab_text}): {size_kb} KB -> {out_file}")
            captured_files.append({"view": tab_text, "path": str(out_file), "size_kb": size_kb})

        browser.close()

    print("\nSuccessfully captured all 8 dashboard view screenshots:")
    for c in captured_files:
        print(f"  - {c['view']}: {c['path']} ({c['size_kb']} KB)")


if __name__ == "__main__":
    capture_all_views()
