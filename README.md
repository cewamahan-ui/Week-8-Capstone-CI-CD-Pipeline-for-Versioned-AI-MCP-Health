# Week 8, CI/CD for Versioned AI + MCP Health

## Overview

AfyaPlus triage now changes safely: prompts, config and the MCP server
are semver-versioned artefacts, and every release lines up one tag
across git, the Docker image, the prompt bundle and the MCP server. A
four-stage pipeline (`lint-test -> eval -> mcp_health -> build-deploy`)
gates every merge to main: the golden-set eval must score at least
**0.85 urgency agreement** with no forbidden dispositions, and the MCP
health probe must complete a handshake and list both required tools
before an image is built and tagged. Rollback is a one-line
`PROMPT_VERSION=1.2.0` on the same image. The model is the Week 6/7
deterministic stub behind the same schema, so the whole capstone runs
at ~$0 API cost.

## Versions

- prompts: **1.2.0** pinned (SHA `5b50e6eafb2ff2ff`), **1.3.0-candidate** on a 10% canary
- config / model_version: `config/triage.yaml` @ 1.3.0-candidate / model `triage-stub-v1` (retrain stub only - no weights trained)
- mcp server: **1.3.0-candidate** (`logistics_mcp_versioned.py` manifest)
- image tag: `afyaplus-triage:v1.3.0-candidate`
- release tag: **v1.3.0-candidate** (git tag = image tag = config `release_tag` = MCP version)
- runtime evidence: `GET /health` reports `prompt_version`, `prompt_sha256_16`, `model_version`, `mcp_server_version`, `release_tag`; `GET /pin` dumps the same facts

```bash
uvicorn prompt_app:app --port 8000
curl -s localhost:8000/health | python -m json.tool
```

## Pipeline
- Green run evidence: https://github.com/cewamahan-ui/Week-8-Capstone-CI-CD-Pipeline-for-Versioned-AI-MCP-Health/actions/runs/36891631794
- GitHub Actions: `.github/workflows/ci.yml` - jobs `lint-test`, `eval`, `mcp_health`, `build-deploy`; triggers on PR + main + `workflow_dispatch`
- Azure DevOps twin: `azure-pipelines.yml` - stages `lint_test`, `eval`, `mcp_health`, `build_deploy`
- Local dry run (act / minute fallback): `python scripts/run_pipeline.py` (or `bash scripts/run_pipeline_local.sh`) - mirrors every stage with the same exit-code contract
- Captured evidence: `evidence/` - full pipeline log, eval pass AND fail, MCP health pass AND fail, pin check, tag alignment, /health snapshot; indexed in `evidence/EVIDENCE_INDEX.md`

**Branch protection (required checks before merge to main):** enable in GitHub repo settings -> Branches -> Add rule for `main`:
- Require a pull request before merging (CODEOWNERS then auto-requests clinical_ops + ml-eng)
- Require status checks to pass: `lint-test (ruff + pytest + pin)`, `eval (golden-set regression gate)`, `mcp-health (handshake + tools probe)`
- Require branches to be up to date before merging

Azure DevOps equivalent: Project settings -> Repos -> Policies -> branch `main` -> require minimum reviewers + a build validation policy pointing at `azure-pipelines.yml`.

Stages in order, fail closed:
1. **lint-test** - ruff, pytest, prompt pin SHA check (`check_prompt_pin.py`)
2. **eval** - golden-set gate (`eval_prompts.py`), non-zero exit blocks everything downstream
3. **mcp_health** - handshake + tools probe (`scripts/check_mcp_health.py`), stub + manifest modes + a self-test that proves the gate can fail
4. **build-deploy** - docker build + tag, digest recorded to the job summary; deploy stub = compose definition on the runner

## Eval gate

- Metric: **urgency agreement** on `evals/golden.jsonl` (12 labelled cases, true JSONL: one object per line, a `_meta` line carries metric + threshold)
- Threshold: **0.85**, stored in the file's `_meta` line (not buried in YAML)
- Quarantine: `fixtures/quarantine.json` - exemptions carry a reason AND an expiry; expired exemptions re-enter the gate (the `E-EXAMPLE` entry demonstrates the rule)
- Per-SHA history: `fixtures/responses/<prompt_sha>.json`
- Failing-run demonstration (the gate is real):
  ```bash
  python eval_prompts.py              # exit 0: score 1.00 >= 0.85
  python eval_prompts.py --self-test  # exit 1: sabotaged classifier scores 0.27, gate blocks
  ```

## MCP health

- Run: `python scripts/check_mcp_health.py` (in-process stub), `--manifest logistics_manifest.json` (offline contract), or `--url http://host:8765/mcp` (live)
- Asserts: initialize handshake, `find_clinic_by_county` + `plan_delivery_route` listed, each tool answers a benign probe call, `clinics://catalog` present
- Exit codes: `0` healthy, `1` contract violation, `2` unreachable - a `1` or `2` in CI stops the pipeline before `build-deploy`
- Fail demonstration: `python scripts/check_mcp_health.py --self-test` (missing tool -> exit 1)

## Runbook and Definition of Done

- `runbook.md` - 01:00 rollback, trace locations, reviewer map, go/no-go sentence, rehearsal log, NCA-GENL domain mapping
- `clinical_ops_change_brief.md` - plain-language change-control brief for clinical_ops
- Sprint DoD checklist for prompt/MCP PRs: `runbook.md` section 9
- Recommend-Against-Decide governance note: `runbook.md` section 10

## Release tagging (the aligned tag, enforced)

```bash
python scripts/make_release_tag.py --check   # verify tag/versions/SHA alignment (CI-safe)
python scripts/make_release_tag.py           # verify + create annotated git tag v1.3.0-candidate
git push origin v1.3.0-candidate             # publish the tag
```

The check verifies `versions.py`, `config/triage.yaml`, `prompts/pin.json`, `logistics_manifest.json` and the pinned prompt SHA all agree on the release identity BEFORE the tag is created - misalignment exits 1 and nothing is tagged.

## Evidence bundle

Regenerate any time: `python scripts/capture_evidence.py`. It runs every gate in both directions, writes the raw logs to `evidence/`, and writes `evidence/EVIDENCE_INDEX.md` mapping each log to the command that produced it. Submitted logs cover: full pipeline pass, eval pass + deliberate fail, MCP health pass + deliberate fail, pin check, tag alignment, /health snapshot.

## Fallbacks declared

- [x] act / workflow_dispatch dry run - `scripts/run_pipeline.py` (shell wrapper provided) mirrors all stages locally; same YAML submitted; logs in `evidence/`
- [x] stub retrain (model_version bump only) - documented in CHANGELOG.md; no weights trained
- [x] local MCP health stub - in-process + manifest probes keep the production exit-code contract
- [x] no paid Azure - azure-pipelines.yml submitted as config-as-code; local script output mirrors each stage (captured in `evidence/`)
- [x] no local Docker - Docker is not installed on the dev laptop, so the docker build/compose stages were verified on the CI runner (and mirrored locally by the compose-validity check); the tagged-image definition is submitted as config
- [x] no paid LLM - golden set evaluated against the deterministic stub behind the Week 6/7 schema; cost $0

## Checklist

- [x] Tag alignment evidenced - `/health` + `logistics_manifest.json` + CHANGELOG alignment table
- [x] Eval fails closed - `--self-test` exit 1, threshold 0.85 in golden.jsonl
- [x] MCP health in the pipeline - enforced job before build-deploy; failure blocks deploy
- [x] Runbook and Definition of Done complete - rollback drill logged, DoD checklist, governance note
- [x] Weeks 6 and 7 reuse documented - below

## Ties to Weeks 6 and 7

| Reused artefact | From | Where in this repo |
|---|---|---|
| FastAPI triage service, models, rule engine | `week 6/triage_api`, `week 7/capstone 7/api` | `triage_stub.py` (same schemas/rules), `prompt_app.py` (same /health + trace habits) |
| MCP server, tools, clinics catalogue, errors-as-data | `week 6/mcp_server/server.py` | `logistics_mcp_versioned.py` + `clinics.json` (copied from `week 6/mcp_server/data/`) |
| Docker slim-base, non-root, HEALTHCHECK, deps-before-code | `week 7/capstone 7/api/Dockerfile` | `deploy/Dockerfile` (+ build ARG version identity) |
| Compose deployment with FinOps/resource habits | `week 7/capstone 7/deploy/docker-compose.cost.yml` | `deploy/docker-compose.yml` (+ mcp_health gate service) |
| Rate-limit, JWT, trace-id patterns | `week 6/triage_api` | `prompt_app.py` trace middleware; env knobs preserved |

## Repository layout (one clear home per deliverable)

```
prompts/ + config/ + versions.py + prompt_loader.py + check_prompt_pin.py   # D1
.github/workflows/ci.yml + azure-pipelines.yml + CODEOWNERS                  # D2
evals/golden.jsonl + fixtures/ + eval_prompts.py + tests/                    # D3
scripts/check_mcp_health.py + logistics_mcp_versioned.py + manifest          # D4
runbook.md + clinical_ops_change_brief.md + CHANGELOG.md                     # D5
scripts/make_release_tag.py                                                  # D1 tag alignment
ab_prompt_flag.py + tool_metrics.py + mcp_dashboard_sketch.py                # Thu labs
scripts/run_pipeline.py + run_pipeline_local.sh + capture_evidence.py        # dry runs + evidence
evidence/ + deploy/                                                          # run logs + deploy stub
```

## How to run

```bash
pip install -r requirements.txt
python check_prompt_pin.py --allow-candidate      # pin integrity
pytest                                             # unit + gate + MCP tests
python eval_prompts.py                             # eval gate (green)
python eval_prompts.py --self-test                 # eval gate (deliberate red)
python scripts/check_mcp_health.py                 # MCP gate (green)
python scripts/check_mcp_health.py --self-test     # MCP gate (deliberate red)
uvicorn prompt_app:app --port 8000                 # app with versioned /health
python scripts/run_pipeline.py                     # full local pipeline
python scripts/capture_evidence.py                 # regenerate evidence/ logs
```

## Secrets

`.env` stays local (gitignored). No key is needed: the stub model and
stub MCP probes run the whole pipeline at $0.
