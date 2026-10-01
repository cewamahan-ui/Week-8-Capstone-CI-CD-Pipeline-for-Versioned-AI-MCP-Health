# Changelog - AfyaPlus triage prompt bundle & release alignment

All notable changes to the prompt bundle, config, MCP server and
release tags. Format: semver, dates 2026. Prompt files are never
edited after release; new text = new version file.

## [1.3.0-candidate] - 2026-09-29 (staged on 10% of staging keys)

### Added
- Prompt rule 6 (`triage_system_v1.3.0-candidate.txt`): ESI-1/ESI-2
  calls now include `"escalation_contact": "on-call-clinician"` so a
  human countersigns every ED dispatch (recommend/decide governance).
- Versioned MCP server (`logistics_mcp_versioned.py`) with a manifest
  asserted by the CI health gate.
- `ab_prompt_flag.py`: deterministic 10% canary bucketing.
- Pipeline gates: `eval` (0.85 threshold) and `mcp_health`.

### Changed
- `config/triage.yaml` now pins prompt 1.2.0 with a named candidate
  and 10% rollout; `mcp.server_version` aligned to the release tag.

### Rollback
- `PROMPT_VERSION=1.2.0` on the same image (runbook.md section 3).

## [1.2.0] - 2026-09-01 (pinned stable)

### Changed
- Prompt rule 3 tightened: the assistant must check the MCP clinic
  catalogue before naming a facility.

### Added
- `prompts/pin.json` - the SHA-256 pin surfaced in `/health`.

## [1.1.0] - 2026-08-18

### Added
- `next_step` operational field on triage responses.

## Retrain stub (no GPU - documented per the brief)

- No weights were trained. `model_version` remains `triage-stub-v1`.
- A retrain job, if run, would: bump `model_version` here, add a
  CHANGELOG line "model_version bumped, no weights trained (stub)",
  and re-run the golden-set gate. The classifier in `triage_stub.py`
  is the documented stand-in behind the same schema.

## Version alignment (the capstone contract)

| Artefact | Version | Where verified |
|---|---|---|
| Release tag | v1.3.0-candidate | git tag, image tag, `/health` |
| Prompt (stable) | 1.2.0 | pin.json SHA `5b50e6eafb2ff2ff`, `/health` |
| Prompt (candidate) | 1.3.0-candidate | 10% canary via ab_prompt_flag.py |
| Config | 1.3.0-candidate | config/triage.yaml service.version |
| MCP server | 1.3.0-candidate | manifest, scripts/check_mcp_health.py |
| model_version | triage-stub-v1 | /health, this file |
