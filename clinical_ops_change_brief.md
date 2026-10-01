# Change-control brief - for the clinical_ops team

From: the AI engineering team
Date: 2026-09-29
Re: a small, careful change to how the triage assistant sorts messages

**Plain-language summary.** We want to try a small improvement to the
instructions our triage assistant follows, on 10% of test traffic
only, and only if every safety check passes first. Nothing changes for
patients until you approve it, and we can undo it in under a minute.

## What changed

The triage prompt moves from version 1.2.0 to 1.3.0-candidate on 10%
of staging keys (staging, not live patients). The change adds one
rule: whenever the assistant flags an emergency-level case, its answer
now also names an on-call clinician who must countersign before an
ambulance is dispatched. The sorting rules themselves - which symptoms
count as urgent - did not change.

## What was tested

Every candidate answer is checked automatically against a fixed set of
12 example cases (the "golden set") that you helped label. The
computer must agree with the labels on at least 85% of cases, and it
may never send an emergency case to routine care. This test runs on
every proposed change; if the score drops, the change is blocked
before a human ever sees it.

## Rollback

Set one setting (`PROMPT_VERSION=1.2.0`) and restart - the previous
version comes back in under a minute, using the same software image.
If the whole release is suspect, redeploy the previous git tag
(`git tag v1.2.0`) which carries the same image and prompt bundle.
The full 01:00 procedure is in `runbook.md`, section 3.

## Who approved

CODEOWNERS requires clinical_ops and ml-eng review on any change to
prompts, eval cases, or config. Approval is recorded on PR #1
(https://github.com/cewamahan-ui/Week-8-Capstone-CI-CD-Pipeline-for-Versioned-AI-MCP-Health/pull/1),
which also carries the green CI gate runs for this change.

## Go or no-go

- **Go** if the evaluation score is green (at least 85% agreement),
  the clinic-lookup tools answer their health check, and the system's
  error rate stays under 10% in staging.
- **No-go** if any of those three fails. A blocked pipeline is the
  system working as intended, not an outage.

## What we ask of you

1. Confirm the golden-set labels still match clinical practice
   (15-minute weekly review).
2. Tell us if the countersign rule adds friction for dispatchers.
3. Reply go/no-go on the PR - that reply is the approval record.
