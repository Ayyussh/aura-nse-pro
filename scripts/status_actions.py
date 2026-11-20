import urllib.request
import json
import sys

def check_runs():
    url = "https://api.github.com/repos/Ayyussh/aura-nse-pro/actions/runs?per_page=6"
    req = urllib.request.Request(url, headers={"User-Agent": "Aura-Runner"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"Failed to fetch runs: {e}")
        return

    runs = data.get("workflow_runs", [])
    print(f"=== GitHub Actions Live Workflows ({len(runs)} most recent) ===")
    for r in runs:
        num = r.get("run_number")
        name = r.get("name")
        status = r.get("status")
        conclusion = r.get("conclusion") or "IN_PROGRESS"
        sha = r.get("head_sha", "")[:7]
        msg = (r.get("head_commit", {}).get("message") or "").splitlines()[0]
        html = r.get("html_url")
        print(f"#{num} [{name}] -> Status: {status.upper()} | Result: {conclusion.upper()} | Commit: {sha} ({msg})")
        print(f"    URL: {html}")

if __name__ == "__main__":
    check_runs()
