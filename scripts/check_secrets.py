"""Fail the build if a secret-looking value is committed or about to be uploaded as an artifact.

  python scripts/check_secrets.py                 scan every git-tracked text file, and fail if .env is tracked
  python scripts/check_secrets.py --paths reports scan these folders/files instead (use before uploading artifacts)

A line containing the marker  secret-scan: allow  is skipped (used only for deliberate fake fixtures in tests).
Findings print file:line and the pattern name, never the matched value.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PATTERNS = {
    "Anthropic API key": re.compile(r"sk-ant-[A-Za-z0-9_-]{24,}"),
    "OpenAI-style API key": re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghs|ghu|ghr)_[A-Za-z0-9]{30,}\b|github_pat_[A-Za-z0-9_]{40,}"),
    "AWS access key id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Private key block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    "Key assigned in config": re.compile(r"(?i)\b(?:anthropic_api_key|api[_-]?key|secret|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{32,}"),
}
ALLOW_MARKER = "secret-scan: allow"
MAX_BYTES = 2_000_000


def scan_text(name: str, text: str) -> list[str]:
    findings = []
    for number, line in enumerate(text.splitlines(), start=1):
        if ALLOW_MARKER in line:
            continue
        for label, pattern in PATTERNS.items():
            if pattern.search(line):
                findings.append(f"{name}:{number}: {label}")
    return findings


def scan_file(path: Path) -> list[str]:
    try:
        if path.stat().st_size > MAX_BYTES:
            return []
        data = path.read_bytes()
    except OSError:
        return []
    if b"\0" in data[:4096]:  # binary
        return []
    return scan_text(path.as_posix(), data.decode("utf-8", errors="replace"))


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], capture_output=True, check=True).stdout.decode("utf-8")
    return [Path(p) for p in out.split("\0") if p]


def expand(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        files.extend(sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [p])
    return files


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paths", nargs="+", help="scan these files/folders instead of git-tracked files")
    args = parser.parse_args(argv)
    findings: list[str] = []
    if args.paths:
        files = expand(args.paths)
    else:
        files = tracked_files()
        findings += [f"{p.as_posix()}: environment file is tracked by git" for p in files if p.name == ".env"]
    for path in files:
        findings += scan_file(path)
    if findings:
        print("Possible secrets found:")
        for item in findings:
            print("  " + item)
        return 1
    print(f"No secrets found in {len(files)} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
