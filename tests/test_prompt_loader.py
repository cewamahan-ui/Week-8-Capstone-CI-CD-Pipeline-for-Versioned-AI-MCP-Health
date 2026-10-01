"""Tests for prompt versioning and pin integrity (Deliverable 1)."""

from __future__ import annotations

import pytest

import prompt_loader
import versions


def test_pinned_version_loads_and_matches_pin():
    p = prompt_loader.load_prompt("1.2.0")
    pin = versions.load_pin()
    assert p["prompt_version"] == "1.2.0"
    assert p["prompt_sha256"] == pin["sha256"]
    assert p["prompt_sha256_16"] == pin["sha256"][:16]
    assert p["is_candidate"] is False


def test_candidate_loads_and_is_marked_candidate():
    p = prompt_loader.load_prompt("1.3.0-candidate")
    assert p["prompt_version"] == "1.3.0-candidate"
    assert p["is_candidate"] is True
    assert p["prompt_sha256"] != versions.load_pin()["sha256"]


def test_health_facts_expose_full_alignment():
    facts = prompt_loader.health_facts()
    for key in (
        "app_version", "prompt_version", "prompt_sha256_16",
        "model_version", "mcp_server_version", "release_tag",
    ):
        assert key in facts and facts[key]
    # The alignment contract: MCP + app share the release-tag semver.
    assert facts["mcp_server_version"] == versions.MCP_SERVER_VERSION


def test_pin_file_and_config_agree_on_versions():
    pin = versions.load_pin()
    cfg_text = (versions.REPO_ROOT / "config" / "triage.yaml").read_text(encoding="utf-8")
    assert pin["prompt_version"] in cfg_text
    assert pin["candidate_version"] in cfg_text


def test_env_override_resolves_version(monkeypatch):
    monkeypatch.setenv("PROMPT_VERSION", "1.3.0-candidate")
    assert versions.resolve_prompt_version() == "1.3.0-candidate"


def test_unknown_version_fails_closed(monkeypatch):
    with pytest.raises(FileNotFoundError):
        prompt_loader.load_prompt("9.9.9")
