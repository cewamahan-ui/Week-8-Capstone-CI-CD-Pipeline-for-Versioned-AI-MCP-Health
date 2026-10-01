#!/usr/bin/env bash
# run_pipeline_local.sh - mirror the CI stages locally (act/fallback path).
#
# Thin wrapper over scripts/run_pipeline.py (cross-platform, one stage
# list). Output and exit-code contract match the YAML pipelines:
# first failing stage stops the run with that exit code. Evidence
# produced here counts as dry-run logs per the brief.

set -uo pipefail
cd "$(dirname "$0")/.."
exec "${PYTHON:-python}" scripts/run_pipeline.py
