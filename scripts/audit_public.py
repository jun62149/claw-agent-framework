"""Inspect the Git index without printing secret values. Exit nonzero on findings."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def audit():
    paths = subprocess.check_output(["git", "ls-files", "--cached", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    paths = [p for p in paths if p]
    if not paths:
        print("FAIL: Git index is empty; stage reviewed files first.")
        return 1
    local_secrets = []
    config = ROOT / "config.json"
    if config.exists():
        values = json.loads(config.read_text(encoding="utf-8"))
        local_secrets = [str(values[k]).encode() for k in
                         ("api_key", "qq_app_id", "qq_app_secret", "feishu_app_id", "feishu_app_secret")
                         if values.get(k) and len(str(values[k])) >= 8]
    pattern = re.compile(rb"(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
    findings = []
    total = 0
    largest = (0, "")
    for path in paths:
        data = subprocess.check_output(["git", "show", f":{path}"], cwd=ROOT)
        total += len(data)
        largest = max(largest, (len(data), path))
        parts = Path(path).parts
        if (Path(path).name == "config.json" or Path(path).name.startswith(".env")
                or any(p in parts for p in (".venv", "__pycache__", "logs", "data_project"))
                or (path.startswith("output/") and not path.startswith("output/skills/"))):
            findings.append((path, "private/runtime file"))
        if len(data) > 5 * 1024 * 1024:
            findings.append((path, "larger than 5 MiB"))
        if any(secret in data for secret in local_secrets):
            findings.append((path, "matches a local credential"))
        # Explicit placeholder in the public configuration template.
        sanitized = data.replace(b"sk-REPLACE_WITH_YOUR_DEEPSEEK_KEY", b"PLACEHOLDER")
        if pattern.search(sanitized):
            findings.append((path, "credential pattern"))
    for path, reason in findings:
        print(f"FAIL: {path}: {reason}")
    print(f"Checked {len(paths)} staged files, {total} bytes; largest: {largest[1]} ({largest[0]} bytes).")
    print(f"Compared against {len(local_secrets)} local credential fields; values never printed.")
    print("FAIL" if findings else "PASS: no configured credential patterns or local credential matches found.")
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(audit())
