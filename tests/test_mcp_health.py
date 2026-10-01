"""Tests for the versioned MCP server + health-gate contract (Deliverables 1 & 4)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check_mcp_health

import logistics_mcp_versioned as mcp


def test_manifest_lists_required_tools_and_version():
    m = mcp.manifest()
    assert set(m["tools"]) == set(check_mcp_health.REQUIRED_TOOLS)
    assert m["server_version"] == mcp.MCP_SERVER_VERSION
    assert m["release_tag"] == mcp.RELEASE_TAG


def test_stub_probe_satisfies_contract():
    probe = check_mcp_health.probe_stub()
    problems = check_mcp_health.assert_contract(probe)
    assert problems == [], problems
    assert probe["handshake"] is True
    assert set(probe["calls"]) == set(check_mcp_health.REQUIRED_TOOLS)
    for tool, outcome in probe["calls"].items():
        assert outcome["ok"], f"{tool}: {outcome}"


def test_contract_fails_on_missing_tool():
    bad = {
        "handshake": True,
        "tools": ["find_clinic_by_county"],
        "resources": ["clinics://catalog"],
    }
    problems = check_mcp_health.assert_contract(bad)
    assert any("plan_delivery_route" in p for p in problems)


def test_contract_fails_on_failed_handshake():
    bad = {"handshake": False, "tools": check_mcp_health.REQUIRED_TOOLS,
           "resources": check_mcp_health.REQUIRED_RESOURCES}
    problems = check_mcp_health.assert_contract(bad)
    assert any("handshake" in p for p in problems)


def test_tools_return_errors_as_data_not_raises():
    r = mcp.find_clinic_by_county("Atlantis")
    assert "error" in r and "known_counties" in r
    r2 = mcp.plan_delivery_route("nairobi", "Atlantis")
    assert "error" in r2


def test_find_clinic_filters_by_service():
    r = mcp.find_clinic_by_county("Kisumu", require_service="icu")
    assert r["count"] == 1  # only JOOTRH has icu in the fixture data
