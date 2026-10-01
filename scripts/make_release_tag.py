#!/usr/bin/env python3
"""make_release_tag.py - create the ONE tag that aligns everything.

Deliverable 1 requires "a release tag that aligns the image tag, the
prompt bundle and the MCP server version". This script is the
enforcement point: it verifies the alignment across versions.py,
config/triage.yaml, pin.json and logistics_manifest.json BEFORE
creating the annotated git tag.

Usage:
  python scripts/make_release_tag.py --check   # verify only (CI-safe)
  python scripts/make_release_tag.py           # verify + git tag v<version>

Exit codes: 0 aligned (tagged if not --check), 1 misalignment found.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import versions  # noqa: E402


def _yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{key}:\s*([^\s#]+)", text, flags=re.MULTILINE)
    return m.group(1) if m else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and create the aligned release tag")
    parser.add_argument("--check", action="store_true", help="verify alignment only, no git tag")
    args = parser.parse_args()

    release = versions.RELEASE_TAG
    expected = f"v{versions.APP_VERSION}"
    problems: list[str] = []

    # 1. Tag itself must be v<app semver>.
    if release != expected:
        problems.append(f"RELEASE_TAG {release} != v{versions.APP_VERSION} (versions.py)")

    # 2. config/triage.yaml agrees.
    cfg_text = (ROOT / "config" / "triage.yaml").read_text(encoding="utf-8")
    cfg_release = _yaml_scalar(cfg_text, "release_tag")
    cfg_service = _yaml_scalar(cfg_text, "version")
    if cfg_release != release:
        problems.append(f"config release_tag={cfg_release} != {release}")
    if cfg_service != versions.APP_VERSION:
        problems.append(f"config service.version={cfg_service} != {versions.APP_VERSION}")

    # 3. MCP manifest agrees.
    manifest = json.loads((ROOT / "logistics_manifest.json").read_text(encoding="utf-8"))
    if manifest.get("release_tag") != release:
        problems.append(f"manifest release_tag={manifest.get('release_tag')} != {release}")
    if manifest.get("server_version") != versions.MCP_SERVER_VERSION:
        problems.append(f"manifest server_version != {versions.MCP_SERVER_VERSION}")

    # 4. MCP server code agrees.
    if versions.MCP_SERVER_VERSION != versions.APP_VERSION:
        problems.append("MCP_SERVER_VERSION != APP_VERSION in versions.py")

    # 5. Pin file names the aligned tag.
    pin = json.loads((ROOT / "prompts" / "pin.json").read_text(encoding="utf-8"))
    if pin.get("aligned_release_tag") != release:
        problems.append(f"pin aligned_release_tag={pin.get('aligned_release_tag')} != {release}")

    # 6. Pinned prompt SHA actually matches the file.
    import hashlib

    prompt_path = ROOT / "prompts" / f"triage_system_v{pin['prompt_version']}.txt"
    if prompt_path.exists():
        actual = hashlib.sha256(prompt_path.read_text(encoding="utf-8").encode()).hexdigest()
        if actual != pin["sha256"]:
            problems.append(f"pin sha256 mismatch for v{pin['prompt_version']}")

    if problems:
        print("TAG-CHECK FAIL:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"TAG-CHECK OK: {release} aligns app={versions.APP_VERSION}, "
          f"mcp={versions.MCP_SERVER_VERSION}, prompt={pin['prompt_version']} "
          f"(sha {pin['sha256'][:16]}), model={versions.MODEL_VERSION}")

    if args.check:
        return 0

    if not (ROOT / ".git").exists():
        print("NOTE: not a git repository here; run `git init` first, then re-run.")
        return 1

    subprocess.run(["git", "tag", "-a", release, "-m",
                    f"AfyaPlus release {release}: app {versions.APP_VERSION}, "
                    f"MCP {versions.MCP_SERVER_VERSION}, prompt {pin['prompt_version']}"],
                   cwd=ROOT, check=True)
    print(f"TAGGED: {release} created. Push with: git push origin {release}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
