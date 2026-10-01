"""Tests for the triage stub rules and the prompt_app /health contract."""

from __future__ import annotations

import pytest

import prompt_app
import triage_stub
from triage_stub import Acuity, Disposition, TriageRequest


def req(symptoms, age=40, **kw):
    return TriageRequest(patient_id=kw.pop("patient_id", "T-1"), symptoms=symptoms,
                         age=age, sex="OTHER", **kw)


def test_critical_maps_to_esi1():
    r = triage_stub.classify(req(["unconscious after fall"]))
    assert r.acuity == Acuity.ESI_1 and r.disposition == Disposition.ED


def test_chest_pain_older_adult_is_esi2_ed():
    r = triage_stub.classify(req(["crushing chest pain", "shortness of breath"], age=58))
    assert r.acuity == Acuity.ESI_2 and r.disposition == Disposition.ED


def test_red_flag_in_young_child_is_esi2():
    r = triage_stub.classify(req(["high fever 39.5C for three days, drowsy"], age=2))
    assert r.acuity == Acuity.ESI_2 and r.disposition == Disposition.ED


def test_moderate_symptoms_urgent_clinic():
    r = triage_stub.classify(req(["persistent vomiting for two days"], age=34))
    assert r.disposition == Disposition.URGENT_CLINIC


def test_mild_symptoms_primary_or_self_care():
    r = triage_stub.classify(req(["mild sore throat, runny nose"], age=22))
    assert r.disposition in {Disposition.PRIMARY_CAT, Disposition.SELF_CAT}
    assert r.acuity in {Acuity.ESI_4, Acuity.ESI_5}


def test_missing_vitals_treated_as_missing_not_zero():
    r = triage_stub.classify(req(["mild headache in the sun"], age=28))
    assert "SpO2" not in r.rationale  # never reasoned from absent data


@pytest.mark.parametrize("field,limit", [("age", 120), ("spo2", 100.0)])
def test_request_bounds_enforced(field, limit):
    data = {"patient_id": "T-9", "symptoms": ["cough"], "age": 30, "sex": "OTHER"}
    data[field] = limit + 1
    with pytest.raises(Exception):
        TriageRequest(**data)


def test_app_health_shape_reports_versions():
    from fastapi.testclient import TestClient

    client = TestClient(prompt_app.app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("app_version", "prompt_version", "prompt_sha256_16",
                "mcp_server_version", "release_tag"):
        assert key in body and body[key]


def test_app_triage_echoes_prompt_version():
    from fastapi.testclient import TestClient

    client = TestClient(prompt_app.app)
    resp = client.post("/triage", json={
        "patient_id": "P-1", "symptoms": ["chest pain"], "age": 58,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["prompt_version"] == "1.2.0"
    assert body["prompt_sha256_16"] == "5b50e6eafb2ff2ff"
