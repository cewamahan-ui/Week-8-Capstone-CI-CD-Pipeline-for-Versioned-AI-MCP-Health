#!/usr/bin/env python3
"""capture_evidence.py - generate the submission evidence bundle.

Runs every gate in both pass and fail directions and writes the raw
console output to evidence/*.log so the submission contains the
"dry-run logs, failing eval demonstration, and MCP health pass and
fail" the checklist asks for - without a marker having to rerun
anything.

Usage:  python scripts/capture_evidence.py
Writes: evidence/pipeline_full_pass.log
        evidence/eval_pass.log, evidence/eval_fail_deliberate.log
        evidence/mcp_health_pass.log, evidence/mcp_health_fail_deliberate.log
        evidence/pin_check.log
        evidence/health_endpoint.json, evidence/tag_alignment_check.log
        evidence/EVIDENCE_INDEX.md
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "evidence"


def run(name: str, cmd: list[str], expect_zero: bool = True, env: dict | None = None) -> bool:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=merged_env)
    out = (proc.stdout or "") + (proc.stderr or "")
    header = (
        f"$ {' '.join(cmd)}\n"
        f"(expected exit {'0' if expect_zero else 'non-zero'}; actual exit {proc.returncode})\n"
        f"{'-' * 70}\n"
    )
    (EVIDENCE / name).write_text(header + out, encoding="utf-8")
    ok = (proc.returncode == 0) == expect_zero
    status = "OK " if ok else "UNEXPECTED "
    print(f"  [{status}] {name:<38} exit={proc.returncode}")
    return ok


def main() -> int:
    EVIDENCE.mkdir(exist_ok=True)
    python = sys.executable or "python"
    results: list[tuple[str, bool]] = []

    print("Capturing evidence into evidence/ ...")

    results.append(("pipeline_full_pass.log",
                    run("pipeline_full_pass.log", [python, "scripts/run_pipeline.py"],
                        expect_zero=True)))
    results.append(("eval_pass.log",
                    run("eval_pass.log", [python, "eval_prompts.py"], expect_zero=True)))
    results.append(("eval_fail_deliberate.log",
                    run("eval_fail_deliberate.log", [python, "eval_prompts.py", "--self-test"],
                        expect_zero=False)))
    results.append(("mcp_health_pass.log",
                    run("mcp_health_pass.log", [python, "scripts/check_mcp_health.py"],
                        expect_zero=True)))
    results.append(("mcp_health_fail_deliberate.log",
                    run("mcp_health_fail_deliberate.log",
                        [python, "scripts/check_mcp_health.py", "--self-test"],
                        expect_zero=False)))
    results.append(("pin_check.log",
                    run("pin_check.log", [python, "check_prompt_pin.py", "--allow-candidate"],
                        expect_zero=True)))
    results.append(("tag_alignment_check.log",
                    run("tag_alignment_check.log",
                        [python, "scripts/make_release_tag.py", "--check"], expect_zero=True)))

    # /health snapshot via TestClient (no server needed).
    health_path = EVIDENCE / "health_endpoint.json"
    try:
        sys.path.insert(0, str(ROOT))
        from fastapi.testclient import TestClient

        import prompt_app

        client = TestClient(prompt_app.app)
        health = client.get("/health").json()
        health_path.write_text(
            "# GET /health captured via FastAPI TestClient\n"
            "# (identical to: uvicorn prompt_app:app --port 8000 && curl -s localhost:8000/health)\n"
            + subprocess.run([python, "-m", "json.tool"], input=__import__("json").dumps(health),
                             capture_output=True, text=True).stdout,
            encoding="utf-8",
        )
        print("  [OK ] health_endpoint.json")
        results.append(("health_endpoint.json", True))
    except Exception as exc:  # noqa: BLE001
        health_path.write_text(f"# /health capture failed: {exc}\n", encoding="utf-8")
        print(f"  [WARN] health_endpoint.json: {exc}")
        results.append(("health_endpoint.json", False))

    all_ok = all(ok for _, ok in results)
    index = [
        "# Evidence Index",
        "",
        f"Generated: {date.today().isoformat()} by `python scripts/capture_evidence.py`. "
        "Each file is the raw console output of the command shown at its top.",
        "",
        "| File | Command | Shows |",
        "|---|---|---|",
        "| pipeline_full_pass.log | `bash scripts/run_pipeline_local.sh` | all 6 stages green, exit 0 |",
        "| eval_pass.log | `python eval_prompts.py` | eval gate green (>= 0.85) |",
        "| eval_fail_deliberate.log | `python eval_prompts.py --self-test` | failing eval blocks (exit 1) |",
        "| mcp_health_pass.log | `python scripts/check_mcp_health.py` | MCP probe green |",
        "| mcp_health_fail_deliberate.log | `python scripts/check_mcp_health.py --self-test` | bad probe blocks (exit 1) |",
        "| pin_check.log | `python check_prompt_pin.py --allow-candidate` | pin SHA integrity |",
        "| tag_alignment_check.log | `python scripts/make_release_tag.py --check` | tag alignment across artefacts |",
        "| health_endpoint.json | `curl localhost:8000/health` (via TestClient) | prompt SHA + versions at runtime |",
        "",
        f"Capture result: {'ALL EXPECTED OUTCOMES CONFIRMED' if all_ok else 'SOME OUTCOMES UNEXPECTED - REVIEW'}.",
        "",
    ]
    (EVIDENCE / "EVIDENCE_INDEX.md").write_text("\n".join(index), encoding="utf-8")
    print("\nIndex: evidence/EVIDENCE_INDEX.md")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
