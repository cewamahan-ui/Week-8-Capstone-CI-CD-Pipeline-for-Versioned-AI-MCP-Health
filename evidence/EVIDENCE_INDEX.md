# Evidence Index

Generated: 2026-10-01 by `python scripts/capture_evidence.py`. Each file is the raw console output of the command shown at its top.

| File | Command | Shows |
|---|---|---|
| pipeline_full_pass.log | `bash scripts/run_pipeline_local.sh` | all 6 stages green, exit 0 |
| eval_pass.log | `python eval_prompts.py` | eval gate green (>= 0.85) |
| eval_fail_deliberate.log | `python eval_prompts.py --self-test` | failing eval blocks (exit 1) |
| mcp_health_pass.log | `python scripts/check_mcp_health.py` | MCP probe green |
| mcp_health_fail_deliberate.log | `python scripts/check_mcp_health.py --self-test` | bad probe blocks (exit 1) |
| pin_check.log | `python check_prompt_pin.py --allow-candidate` | pin SHA integrity |
| tag_alignment_check.log | `python scripts/make_release_tag.py --check` | tag alignment across artefacts |
| health_endpoint.json | `curl localhost:8000/health` (via TestClient) | prompt SHA + versions at runtime |

Capture result: ALL EXPECTED OUTCOMES CONFIRMED.
