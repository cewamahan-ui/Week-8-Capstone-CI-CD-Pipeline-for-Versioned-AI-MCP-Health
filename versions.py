"""Versioning and pinning for the AfyaPlus triage prompt bundle.

All version numbers live here (or in config/triage.yaml) and every
artefact agrees: prompts, config, MCP server, image tag, git tag.

Semver rules for this repo:
  MAJOR = changed output contract (acuity/disposition meanings moved)
  MINOR = new example or wording that may shift outputs
  PATCH = typo/formatting only, outputs unchanged
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PROMPTS_DIR = REPO_ROOT / "prompts"

DEFAULT_PROMPT_VERSION = "1.2.0"

APP_VERSION = "1.3.0-candidate"          # triage service semver
MCP_SERVER_VERSION = "1.3.0-candidate"   # logistics MCP server semver
MODEL_VERSION = "triage-stub-v1"         # retrain stub only bumps this

# The release tag that must align across git, image, prompt bundle, MCP.
RELEASE_TAG = "v1.3.0-candidate"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_text(path.read_text(encoding="utf-8"))


def expected_prompt_sha(version: str) -> str:
    """Full SHA-256 of the named prompt file (16-char prefix used at runtime)."""
    return sha256_file(PROMPTS_DIR / f"triage_system_v{version}.txt")


def load_pin() -> dict:
    with (PROMPTS_DIR / "pin.json").open("r", encoding="utf-8") as fh:
        return json.load(fh)


def resolve_prompt_version() -> str:
    """PROMPT_VERSION env wins, then config, then the pinned default."""
    import os

    env = os.getenv("PROMPT_VERSION", "").strip()
    if env:
        return env
    try:
        import yaml  # optional at runtime

        cfg = yaml.safe_load((REPO_ROOT / "config" / "triage.yaml").read_text(encoding="utf-8"))
        return str(cfg.get("prompt_version", DEFAULT_PROMPT_VERSION))
    except ImportError:
        return DEFAULT_PROMPT_VERSION
    except FileNotFoundError:
        return DEFAULT_PROMPT_VERSION


def load_prompt_text(version: str | None = None) -> str:
    version = version or resolve_prompt_version()
    path = PROMPTS_DIR / f"triage_system_v{version}.txt"
    return path.read_text(encoding="utf-8")
