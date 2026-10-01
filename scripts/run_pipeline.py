#!/usr/bin/env python3
"""run_pipeline.py - cross-platform mirror of the CI stages.

Same stage order and exit-code contract as the YAML pipelines: the
first failing stage stops the run with that exit code. Invoked by
scripts/run_pipeline_local.sh (human path) and scripts/capture_evidence.py
(evidence path) so there is exactly ONE stage list to keep in sync.

Usage: python scripts/run_pipeline.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _ruff_cmd() -> list[str]:
    """Prefer the executable; fall back to the module invocation."""
    if shutil.which("ruff"):
        return ["ruff", "check", "."]
    return [sys.executable, "-m", "ruff", "check", "."]


def main() -> int:
    python = sys.executable or "python"
    # Each entry is a single argv list (exact parity with the CI YAML);
    # flags must live in the same list as the script path so argparse
    # sees them.
    stages: list[tuple[str, list[str]]] = [
        ("lint (ruff)", _ruff_cmd()),
        ("pin (prompt integrity)", [python, "check_prompt_pin.py", "--allow-candidate"]),
        ("test (pytest)", [python, "-m", "pytest"]),
        ("eval (golden-set gate)", [python, "eval_prompts.py"]),
        ("mcp_health (stub probe)", [python, "scripts/check_mcp_health.py"]),
        ("mcp_health (manifest)",
         [python, "scripts/check_mcp_health.py", "--manifest", "logistics_manifest.json"]),
    ]

    print()
    for i, (name, cmd) in enumerate(stages, 1):
        print("=" * 67)
        print(f" STAGE {i}: {name}")
        print("=" * 67)
        proc = subprocess.run(cmd, cwd=ROOT)
        if proc.returncode != 0:
            print(f"[FAIL] {name} (exit {proc.returncode})")
            print()
            print(f"PIPELINE BLOCKED at stage {i} - deploy stub not attempted (fail closed).")
            return proc.returncode
        print(f"[PASS] {name}")

    print()
    print("ALL STAGES PASSED - deploy stub would proceed: "
          "docker compose -f deploy/docker-compose.yml up -d")
    return 0


if __name__ == "__main__":
    sys.exit(main())
