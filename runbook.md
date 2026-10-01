# LLMOps Runbook - AfyaPlus Triage (Week 8 Capstone)

Owner: ml-eng on-call | Clinical contact: clinical_ops lead
Last rehearsed: 2026-09-29 (rollback drill, see Rehearsal log)

---

## 1. What is deployed and how versions line up

One release = one tag everywhere. If these four disagree, stop and
escalate - something deployed out of band.

| Artefact | Where it lives | Check |
|---|---|---|
| Release tag | git tag + image tag | `afyaplus-triage:v1.3.0-candidate` |
| Prompt bundle | `prompts/` + `prompts/pin.json` | `/health` shows `prompt_sha256_16` |
| Config | `config/triage.yaml` | `service.release_tag` must equal the tag above |
| MCP server | `logistics_mcp_versioned.py` manifest | probe output `server_version` |

Verify alignment in 30 seconds:

```bash
curl -s http://localhost:8000/health | python -m json.tool
python check_prompt_pin.py --allow-candidate
python scripts/check_mcp_health.py --manifest logistics_manifest.json
python scripts/make_release_tag.py --check   # enforces the alignment, CI-safe
```

`/health` reports: `app_version`, `prompt_version`,
`prompt_sha256_16`, `model_version`, `mcp_server_version`,
`release_tag`. If `prompt_sha256_16` does not match `pin.json`, the
running container is serving unverified text - treat as an incident.

## 2. Rolling FORWARD (normal deploy)

1. Open a PR changing only versioned artefacts (`prompts/`, `config/`,
   `evals/`) or code. CODEOWNERS routes prompt/config changes to
   clinical_ops + ml-eng.
2. CI must pass all gates, in order:
   `lint-test` (ruff + pytest + pin) -> `eval` (golden-set >= 0.85,
   no must_not violation) -> `mcp_health` (handshake + required tools)
   -> `build-deploy` (docker build + tag, digest recorded).
   Branch protection makes the first three REQUIRED status checks on
   main - a red gate cannot be merged around (see README, Branch
   protection).
3. Merge. Tag the release: `python scripts/make_release_tag.py`
   (verifies alignment, then creates the annotated tag), then
   `git push origin v<semver>`.
4. Deploy stub (no cloud in the capstone):
   `docker compose -f deploy/docker-compose.yml up -d --build`.
5. Post-deploy check: `/health` shows the new `prompt_version` and
   matching SHA; `python mcp_dashboard_sketch.py` shows error_rate
   under the 0.10 gate.

## 3. Rolling BACK (01:00 procedure - no thinking required)

The image carries every prompt version. Rollback does not rebuild
anything and does not need the repo.

```bash
# Option A (preferred): redeploy the previous image tag.
docker compose -f deploy/docker-compose.yml down
docker compose -f deploy/docker-compose.yml up -d \
  -e PROMPT_VERSION=1.2.0 afyaplus_triage_w8   # env pin, same image

# Option B: same image, pin the stable bundle.
PROMPT_VERSION=1.2.0 docker compose -f deploy/docker-compose.yml up -d

# Verify the rollback took:
curl -s http://localhost:8000/health | grep prompt_version   # expect 1.2.0
```

If the MCP server is the problem (probe failing):

```bash
python scripts/check_mcp_health.py   # exit 1 = contract broken, exit 2 = unreachable
```

A red MCP probe blocks deploy by design. To restore service while
investigating, redeploy the previous release tag of the image; the MCP
tools are deterministic and version-pinned, so the old tag behaves.

Git-level rollback (when the bad change is merged to main):
`git revert <merge-commit>` opens a PR; the same gates run on it.

## 4. Where traces live

| Signal | Location |
|---|---|
| Request trace id | `x-trace-id` response header; echoed in every log line |
| Eval runs | `fixtures/responses/<prompt_sha>.json` (per-sha history) |
| Tool counters | `tool_metrics.STORE` -> `python mcp_dashboard_sketch.py --json` |
| CI evidence | Actions run logs; local dry-run logs captured in `evidence/` (see `evidence/EVIDENCE_INDEX.md`) |
| Quarantine exemptions | `fixtures/quarantine.json` (reason + expiry, reviewed monthly) |

## 5. Who reviews clinical-adjacent prompts

Per `.github/CODEOWNERS`: any change to `prompts/`, `evals/`,
`config/`, or `fixtures/quarantine.json` requires **clinical_ops**
approval plus ml-eng. No exceptions, including "just wording" changes
- wording is behaviour for an LLM. The weekly review is 15 minutes:
new quarantine entries, error-rate trend, and any must_not hits.

## 6. Go / no-go rule (the one sentence)

Deploy proceeds only if eval is green (>= 0.85 urgency agreement, no
must_not violation), the MCP handshake lists `find_clinic_by_county`
and `plan_delivery_route`, and staging error_rate stays under 0.10.

## 7. Rehearsal log

| Date | Drill | Result |
|---|---|---|
| 2026-09-29 | Eval self-test (deliberate regression) | gate failed closed, exit 1 |
| 2026-09-29 | MCP self-test (missing tool) | probe failed, exit 1, deploy blocked |
| 2026-09-29 | Rollback rehearsal: PROMPT_VERSION=1.2.0 on candidate container | /health showed 1.2.0 in < 1 min |
| 2026-09-29 | Full local pipeline (scripts/run_pipeline_local.sh) | 6/6 stages passed, exit 0, deploy stub reached |

## 8. NCA-GENL domain map (what this repo certifies)

| Deliverable | Domain | Marker evidence |
|---|---|---|
| 1. Versioned prompts/config/MCP | Deployment & operational capability | aligned tags; SHA visible in /health |
| 2. Pipeline YAML | Deployment & operational capability | gated workflow, exact check names, run logs |
| 3. Eval + regression gate | Evaluation & model assessment | metric 0.85 threshold; failing run blocked merge |
| 4. MCP health in CI | Architecture & integration | probe asserted pre-deploy, fails closed |
| 5. Runbook + DoD | Communication & stakeholder objective | this document; plain-language brief |

## 9. Sprint Definition of Done - prompt & MCP PRs

A prompt/MCP PR is **Done** when every box is checked:

- [ ] New prompt text lives in a NEW version file (never edit a released file)
- [ ] `prompts/pin.json` updated: version + full SHA-256
- [ ] `config/triage.yaml` `prompt_version` points at a file that exists
- [ ] `python check_prompt_pin.py --allow-candidate` passes locally
- [ ] Golden set evaluated: `python eval_prompts.py` exits 0 (>= 0.85, no must_not)
- [ ] Any quarantined case has a reason AND an expiry in `fixtures/quarantine.json`
- [ ] MCP probe passes: `python scripts/check_mcp_health.py` exits 0
- [ ] `/health` output pasted in the PR showing new version + SHA
- [ ] clinical_ops approval recorded (CODEOWNERS auto-request)
- [ ] CHANGELOG.md updated (version, date, what changed, rollback note)
- [ ] If retrain: model_version bumped + CHANGELOG line stating no weights trained (stub)

## 10. Recommend - Against - Decide (governance note)

AfyaPlus-style deployments classify every AI change into one of three
lanes, and the pipeline enforces the lanes:

| Lane | Meaning | Examples | Human requirement |
|---|---|---|---|
| **Recommend** | AI output is advisory; a human can ignore it | clinic lookup, delivery-route hints | reviewer may be the requester; eval gate still applies |
| **Against** | AI may veto or block an action | none today; example would be auto-refusing a referral | prohibited without explicit clinical_ops + sponsor sign-off; not enabled in this repo |
| **Decide** | AI output acts without a human | none today; example would be auto-dispatching ambulances | prohibited in this capstone; requires regulator-level review, formal clinical trial, and a named accountable clinician |

Rule of thumb: triage sorting may *recommend*; only a clinician may
*decide*. The `escalation_contact` field added in 1.3.0 exists exactly
to keep high-acuity outputs on the recommend side of the line. Any PR
that would move a behaviour up a lane must add a row here and cannot
merge on engineering approval alone.
