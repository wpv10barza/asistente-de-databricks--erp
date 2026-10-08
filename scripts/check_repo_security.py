#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path("scripts/check_repo_security.py")

PATTERNS = {
    "Google API key": re.compile("AI" + "za[0-9A-Za-z_-]{30,}"),
    "GitHub token": re.compile("gh" + "p_[A-Za-z0-9]{30,}"),
    "AWS access key": re.compile("AK" + "IA[0-9A-Z]{16}"),
}

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".rar", ".7z"}


def tracked_files() -> list[Path]:
    raw = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return [ROOT / item.decode() for item in raw.split(b"\0") if item]


findings: list[str] = []
for path in tracked_files():
    relative = path.relative_to(ROOT)
    if relative == SELF or path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
        continue
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue

    marker = "-----BEGIN " + "PRIVATE KEY-----"
    if marker in content:
        findings.append(f"{relative}: private key material")

    for name, pattern in PATTERNS.items():
        if pattern.search(content):
            findings.append(f"{relative}: {name}")

if findings:
    print("SECRET_SCAN_FAILED")
    for finding in findings:
        print(" -", finding)
    raise SystemExit(1)

print("SECRET_SCAN_OK")
