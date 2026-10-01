"""Tests for the golden-set regression gate (Deliverable 3)."""

from __future__ import annotations

import eval_prompts


def test_gate_passes_on_pinned_bundle():
    report = eval_prompts.run_eval("1.2.0")
    assert report["passed"] is True, report["hard_failures"]
    assert report["eval_score"] >= report["threshold"]
    assert report["hard_failures"] == []


def test_gate_fails_closed_on_sabotage():
    eval_prompts._SABOTAGE = True
    try:
        report = eval_prompts.run_eval()
    finally:
        eval_prompts._SABOTAGE = False
    assert report["passed"] is False
    assert report["eval_score"] < report["threshold"]


def test_quarantine_excludes_expired_and_admits_current():
    q = eval_prompts.load_quarantined()
    # G-010 is quarantined with expiry 2026-10-31 (after today) -> present.
    assert "G-010" in q
    assert q["G-010"]  # a reason is recorded, never blank


def test_golden_labels_are_wellformed():
    golden = eval_prompts.load_golden()
    assert float(golden["threshold"]) == 0.85
    assert len(golden["cases"]) >= 10
    for case in golden["cases"]:
        assert case["label"].startswith("ESI-")
        assert case["disposition"] in {"ED", "URGENT_CLINIC", "PRIMARY_CARE", "SELF_CARE"}


def test_eval_report_is_persisted_by_sha():
    report = eval_prompts.run_eval("1.2.0")
    assert report["results_file"]
    assert report["prompt_sha256_16"] in report["results_file"]
