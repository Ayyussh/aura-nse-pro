import subprocess
import re

out = subprocess.check_output(["git", "log", "-p"], text=True, errors="ignore")
patterns = {
    "Google Gemini API Key": r"AIza[0-9A-Za-z-_]{35}",
    "OpenAI Secret Key": r"sk-[a-zA-Z0-9]{32,}",
    "GitHub Personal Access Token": r"ghp_[a-zA-Z0-9]{36}",
    "Telegram Bot Token": r"[0-9]{9,10}:[a-zA-Z0-9_-]{35}",
    "Private Key Header": r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
    "Generic Hardcoded Secret": r"(?i)(?:api_key|secret_key|private_key|auth_token)\s*=\s*['\"][a-zA-Z0-9_\-]{16,}['\"]",
}

found = {}
for name, pat in patterns.items():
    matches = re.findall(pat, out)
    # Filter out placeholder strings like your_telegram_bot_token_here
    filtered = [m for m in matches if not any(ph in m.lower() for ph in ["your_", "example", "placeholder", "xxx"])]
    if filtered:
        found[name] = set(filtered)

print("=== GIT HISTORY SECRETS SCAN REPORT ===")
if not found:
    print("CLEAN: Zero active secrets or credentials detected across all git commits.")
else:
    for name, matches in found.items():
        print(f"WARNING: Potential {name} found: {len(matches)} occurrences")
