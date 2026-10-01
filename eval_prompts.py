#!/usr/bin/env python3
"""eval_prompts.py - the Deliverable 3 regression gate.

Compares the classifier's answers for the golden set against the
pinned labels and prints one number:

    eval_score = urgency agreement rate over eligible cases

Eligible = not in fixtures/quarantine.json (each exemption there must
carry a reason and an expiry, and expired ones are re-admitted - i.e.
they start counting against you again).

Gate rule (fails closed, exit 1):
    eval_score >= evals/golden.jsonl "threshold" (0.85)
    AND no case hits its "must_not" dispositions (hard fail per case)

The classifier is the Week 6/7 stub behind the same schema, so cost is
zero; swapping in a live LLM call later changes only `classify_case`
below. Output is a single JSON line so CI logs stay greppable.

Usage:
  python eval_prompts.py                      # pinned (1.2.0) bundle
  python eval_prompts.py --prompt-version 1.3.0-candidate
  python eval_prompts.py --self-test          # failing-gate demo
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GOLDEN_PATH = ROOT / "evals" / "golden.jsonl"
QUARANTINE_PATH = ROOT / "fixtures" / "quarantine.json"
RESULTS_DIR = ROOT / "fixtures" / "responses"

sys.path.insert(0, str(ROOT))

import prompt_loader  # noqa: E402
import versions  # noqa: E402
from triage_stub import TriageRequest  # noqa: E402

# Stub labels differ from the golden vocabulary in two places.
DISPOSITION_ALIASES = {
    "URGENT_CLINIC": "URGENT_CLINIC",
    "PRIMARY_CARE": "PRIMARY_CARE",
    "ED": "ED",
    "SELF_CARE": "SELF_CARE",
}

# Set True only by --self-test to simulate a broken classifier.
_SABOTAGE = False


def classify_case(case: dict) -> dict:
    """One golden case -> model answer. Deterministic stub, zero API cost."""
    if _SABOTAGE:
        # Regression simulation: everything looks mild. The gate must
        # catch exactly this kind of silent quality collapse.
        return {"id": case["id"], "acuity": "ESI-4", "disposition": "SELF_CARE"}
    req = TriageRequest(
        patient_id=f"GOLDEN-{case['id']}",
        symptoms=[case["input"]],
        age=_age_of(case["input"]),
        sex="OTHER",
    )
    resp = __import__("triage_stub").classify(req)
    return {
        "id": case["id"],
        "acuity": resp.acuity.value if hasattr(resp.acuity, "value") else str(resp.acuity),
        "disposition": str(resp.disposition),
    }


def _age_of(text: str) -> int:
    import re

    m = re.search(r"(\d+)[- ]year", text.lower())
    return int(m.group(1)) if m else 40


def load_quarantined() -> dict[str, str]:
    """Unexpired exemptions only. Expired ones re-enter the gate."""
    if not QUARANTINE_PATH.exists():
        return {}
    data = json.loads(QUARANTINE_PATH.read_text(encoding="utf-8"))
    quarantined: dict[str, str] = {}
    today = date.today().isoformat()
    for item in data.get("exemptions", []):
        expiry = item.get("expires", "")
        if expiry and expiry >= today:  # expired exemptions re-admitted
            quarantined[item["id"]] = item.get("reason", "no reason recorded")
    return quarantined


def load_golden() -> dict:
    """Accept true JSONL (one object per line, a {_meta: true} line may
    carry metric/threshold) AND the legacy pretty-printed shape, so
    the gate works whichever a student submitted."""
    raw = GOLDEN_PATH.read_text(encoding="utf-8")
    stripped = raw.strip()
    if stripped.startswith("{") and "\n" in stripped and '"_meta"' in stripped:
        cases = []
        meta: dict = {}
        for line in stripped.splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("_meta"):
                meta = obj
            else:
                cases.append(obj)
        return {
            "cases": cases,
            "threshold": float(meta.get("threshold", 0.85)),
            "metric": meta.get("metric", "urgency_agreement"),
        }
    data = json.loads(stripped)
    if isinstance(data, dict) and "cases" in data:
        return data
    # .jsonl shape: one case per line, no meta line
    cases = [json.loads(line) for line in stripped.splitlines() if line.strip()]
    return {"cases": cases, "threshold": 0.85, "metric": "urgency_agreement"}


def run_eval(prompt_version: str | None = None) -> dict:
    golden = load_golden()
    quarantined = load_quarantined()
    threshold = float(golden.get("threshold", 0.85))

    p = prompt_loader.load_prompt(prompt_version)
    results: list[dict] = []
    eligible = 0
    agreements = 0

    for case in golden["cases"]:
        got = classify_case(case)
        quarantined_reason = quarantined.get(case["id"])
        label_ok = got["acuity"] == case["label"]
        disp = DISPOSITION_ALIASES.get(str(got["disposition"]), str(got["disposition"]))
        disp_ok = disp == case["disposition"]
        must_not_hits = sorted(set(case.get("must_not", [])) & {disp})
        hard_fail = bool(must_not_hits)

        if quarantined_reason is None:
            eligible += 1
            if label_ok:
                agreements += 1

        results.append(
            {
                "id": case["id"],
                "expected_acuity": case["label"],
                "got_acuity": got["acuity"],
                "label_ok": label_ok,
                "expected_disposition": case["disposition"],
                "got_disposition": disp,
                "disposition_ok": disp_ok,
                "must_not_violation": must_not_hits,
                "hard_fail": hard_fail,
                "quarantined": quarantined_reason,
            }
        )

    score = round(agreements / eligible, 4) if eligible else 0.0
    hard_failures = [r for r in results if r["hard_fail"] and not r["quarantined"]]
    passed = score >= threshold and not hard_failures

    report = {
        "metric": golden.get("metric", "urgency_agreement"),
        "eval_score": score,
        "threshold": threshold,
        "eligible_cases": eligible,
        "agreements": agreements,
        "quarantined_count": len(quarantined),
        "hard_failures": [r["id"] for r in hard_failures],
        "prompt_version": p["prompt_version"],
        "prompt_sha256_16": p["prompt_sha256_16"],
        "model_version": versions.MODEL_VERSION,
        "passed": passed,
        "results": results,
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"{p['prompt_sha256_16']}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["results_file"] = str(out.relative_to(ROOT))
    return report


def self_test() -> int:
    """Deliberate failing run: a broken classifier must fail the gate.

    Uses the module-level _SABOTAGE flag rather than unittest.mock so
    the sabotage applies even when this file is run as a script
    (where __main__ and eval_prompts are distinct module objects).
    """
    global _SABOTAGE
    _SABOTAGE = True
    try:
        report = run_eval()
    finally:
        _SABOTAGE = False
    print("--- SELF-TEST (deliberately broken classifier) ---")
    print(json.dumps({k: report[k] for k in
                      ("eval_score", "threshold", "hard_failures", "passed")}, indent=2))
    if report["passed"]:
        print("SELF-TEST UNEXPECTED: gate passed while classifier was broken - gate is fake!")
        return 1
    print("SELF-TEST OK: gate failed closed on the regression (exit 1 is the demonstration).")
    return 1  # the deliberate failure IS the successful demonstration


def main() -> int:
    parser = argparse.ArgumentParser(description="Golden-set eval gate")
    parser.add_argument("--prompt-version", default=None)
    parser.add_argument("--self-test", action="store_true",
                        help="run a deliberately failing gate to prove it fails closed")
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    report = run_eval(args.prompt_version)
    summary = {k: report[k] for k in
               ("metric", "eval_score", "threshold", "eligible_cases",
                "quarantined_count", "hard_failures", "prompt_version",
                "prompt_sha256_16", "passed", "results_file")}
    print("EVAL " + json.dumps(summary))
    if not report["passed"]:
        failing = [r for r in report["results"] if (not r["label_ok"] and not r["quarantined"])]
        print("EVAL FAIL detail:")
        for r in failing:
            print(f"  {r['id']}: expected {r['expected_acuity']}, got {r['got_acuity']}")
        for r in report["results"]:
            if r["must_not_violation"] and not r["quarantined"]:
                print(f"  {r['id']}: must_not violated with {r['got_disposition']}")
        return 1
    print("EVAL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
