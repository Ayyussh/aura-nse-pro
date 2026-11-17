"""AURA-NSE Pro Git History Purge Preparation & Dry-Run Auditor (Section 21.2 Item 5).

Audits and prepares the removal of historical `reports/` and `data/` artifacts from git history.
IMPORTANT: Rewriting git commit history changes commit SHAs and requires force-pushing.
Execution is STRICTLY an OWNER_ACTION requiring explicit user confirmation.

Usage:
    python scripts/purge_git_history.py           # Dry-run audit (Default & Safe)
    python scripts/purge_git_history.py --execute # Requires OWNER_ACTION confirmation
"""

from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any

_project_root = Path(__file__).resolve().parent.parent


def get_git_tracked_history_files() -> List[str]:
    """Inspect git tree history for files under reports/ and data/."""
    cmd = ["git", "log", "--name-only", "--pretty=format:", "--diff-filter=A", "--", "reports", "data"]
    try:
        res = subprocess.run(cmd, cwd=str(_project_root), capture_output=True, text=True, check=True)
        files = set()
        for line in res.stdout.splitlines():
            line = line.strip()
            if line and (line.startswith("reports/") or line.startswith("data/")):
                files.add(line)
        return sorted(list(files))
    except Exception as e:
        print(f"Error querying git log: {e}")
        return []


def run_dry_run_audit():
    print("=" * 70)
    print("AURA-NSE Pro Git History Purge Audit (DRY-RUN)")
    print("=" * 70)
    print("Status: OWNER_ACTION (Dry-run mode, zero repository modifications made)")
    print("\nScanning repository commit history for tracked reports/ and data/ blobs...")

    files = get_git_tracked_history_files()
    print(f"\nFound {len(files)} historical file paths recorded across commits in reports/ and data/:")
    for f in files[:20]:
        print(f"  - {f}")
    if len(files) > 20:
        print(f"  ... and {len(files) - 20} more files.")

    print("\n" + "-" * 70)
    print("RECOMMENDED OWNER COMMANDS TO PURGE HISTORY:")
    print("-" * 70)
    print("Option A (Using git-filter-repo - recommended):")
    print("  pip install git-filter-repo")
    print("  git filter-repo --path reports/ --path data/ --invert-paths")
    print("\nOption B (Using git filter-branch):")
    print("  git filter-branch --force --index-filter \\")
    print("    'git rm -rf --cached --ignore-unmatch reports/ data/' \\")
    print("    --prune-empty --tag-name-filter cat -- --all")
    print("-" * 70)
    print("Safety Notice: Once purged, run 'git push origin --force --all'.")
    print("Status remains: OWNER_ACTION.")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Git History Purge Tool")
    parser.add_argument("--execute", action="store_true", help="Execute the history purge (requires confirmation)")
    args = parser.parse_args()

    if not args.execute:
        run_dry_run_audit()
    else:
        print("\n⚠️ OWNER_ACTION REQUIRED: Modifying git history is an owner-level action.")
        print("To proceed, run: git filter-repo --path reports/ --path data/ --invert-paths")
        sys.exit(0)


if __name__ == "__main__":
    main()
