#!/usr/bin/env python3
"""check_prompt_pin.py - fail closed when the pin does not match reality.

Exit codes:
  0  pinned version file exists and its SHA-256 matches pin.json
  1  pin or file missing, SHA mismatch, or malformed pin
  2  candidate bundle referenced but file missing (config drift)

Run in CI (lint stage) and before any deploy:
  python check_prompt_pin.py
  python check_prompt_pin.py --allow-candidate   # tolerate candidate drift
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROMPTS = ROOT / "prompts"
PIN_PATH = PROMPTS / "pin.json"
CONFIG_PATH = ROOT / "config" / "triage.yaml"


def _sha256_text(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fail(msg: str, code: int) -> int:
    print(f"PIN-CHECK FAIL: {msg}")
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify prompt pin integrity")
    parser.add_argument("--allow-candidate", action="store_true",
                        help="also verify the candidate bundle if config names one")
    args = parser.parse_args()

    # 1. Pin must exist and be well-formed.
    if not PIN_PATH.exists():
        return _fail(f"{PIN_PATH} missing", 1)
    try:
        pin = json.loads(PIN_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return _fail(f"pin.json is not valid JSON: {exc}", 1)
    for field in ("prompt_version", "sha256"):
        if not pin.get(field):
            return _fail(f"pin.json missing required field '{field}'", 1)

    # 2. Pinned file must exist and match the recorded SHA.
    pinned_version = pin["prompt_version"]
    prompt_path = PROMPTS / f"triage_system_v{pinned_version}.txt"
    if not prompt_path.exists():
        return _fail(f"pinned prompt file {prompt_path.name} missing", 1)
    actual_sha = _sha256_text(prompt_path.read_text(encoding="utf-8"))
    if actual_sha != pin["sha256"]:
        return _fail(
            f"SHA mismatch for v{pinned_version}: pin says {pin['sha256'][:16]}, "
            f"file is {actual_sha[:16]}",
            1,
        )
    print(f"PIN-CHECK OK: v{pinned_version} sha={actual_sha[:16]}")

    # 3. Candidate drift check (optional, useful before staging deploys).
    if args.allow_candidate:
        candidate = pin.get("candidate_version")
        if candidate:
            cand_path = PROMPTS / f"triage_system_v{candidate}.txt"
            if not cand_path.exists():
                return _fail(f"candidate {candidate} named in pin but file missing", 2)
            print(f"PIN-CHECK OK: candidate v{candidate} present")

    # 4. Config must name a version that exists on disk.
    if CONFIG_PATH.exists():
        text = CONFIG_PATH.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.split("#", 1)[0].strip()  # drop trailing comments
            if stripped.startswith("prompt_version:"):
                cfg_version = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                cfg_path = PROMPTS / f"triage_system_v{cfg_version}.txt"
                if not cfg_path.exists():
                    return _fail(f"config prompt_version {cfg_version} has no file", 1)
                print(f"PIN-CHECK OK: config prompt_version={cfg_version} exists")
                break

    print("PIN-CHECK PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
