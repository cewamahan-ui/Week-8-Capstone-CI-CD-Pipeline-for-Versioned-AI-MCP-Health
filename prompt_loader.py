"""Loader for the versioned triage prompt bundle.

Deliverable 1: the running app must know exactly which prompt text it
is serving, and /health must expose the version + SHA so anyone can
verify the pin against prompts/pin.json.
"""

from __future__ import annotations

import versions


class PromptPinError(RuntimeError):
    """Raised when the loaded prompt does not match the pin."""


def current_version() -> str:
    return versions.resolve_prompt_version()


def load_prompt(version: str | None = None) -> dict:
    """Load prompt text for a version and verify its SHA against pin.json.

    The pin records the stable bundle (1.2.0). A candidate version is
    allowed to deviate - that is the point of a candidate - but the pin
    itself must still match the file it names, or startup fails.
    """
    v = version or current_version()
    text = versions.load_prompt_text(v)
    sha = versions.sha256_text(text)

    pin = versions.load_pin()
    pinned_version = pin["prompt_version"]
    pinned_sha = pin["sha256"]

    if v == pinned_version and sha != pinned_sha:
        raise PromptPinError(
            f"prompt v{v} SHA {sha[:16]} does not match pin {pinned_sha[:16]} "
            "- refusing to serve an unverified bundle"
        )
    if sha == pinned_sha and v != pinned_version:
        # Serving pinned bytes under a different label would poison
        # rollback evidence. Refuse the mislabel.
        raise PromptPinError(
            f"version {v} carries the pinned 1.2.0 bytes; relabel or fix pin.json"
        )

    return {
        "prompt_version": v,
        "prompt_text": text,
        "prompt_sha256": sha,
        "prompt_sha256_16": sha[:16],
        "pinned_version": pinned_version,
        "is_candidate": v != pinned_version,
    }


def health_facts() -> dict:
    """Facts /health reports so the runtime pin is externally verifiable."""
    p = load_prompt()
    pin = versions.load_pin()
    return {
        "app_version": versions.APP_VERSION,
        "prompt_version": p["prompt_version"],
        "prompt_sha256_16": p["prompt_sha256_16"],
        "model_version": versions.MODEL_VERSION,
        "mcp_server_version": versions.MCP_SERVER_VERSION,
        "release_tag": versions.RELEASE_TAG,
        "pinned_prompt_version": pin["prompt_version"],
        "candidate_rollout_percent": pin.get("candidate_rollout_percent", 0)
        if p["is_candidate"]
        else 0,
    }
