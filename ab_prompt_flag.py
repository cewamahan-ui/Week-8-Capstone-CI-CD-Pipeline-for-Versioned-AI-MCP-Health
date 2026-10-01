#!/usr/bin/env python3
"""ab_prompt_flag.py - Thursday Lab 1: split staging traffic across prompts.

Deterministic 10% canary: the same patient_id always lands in the same
arm (hash bucketing, not randomness), so a replayed request never flips
variants mid-treatment. The candidate arm serves PROMPT_VERSION
1.3.0-candidate; everyone else gets the pinned 1.2.0.

Usage:
  python ab_prompt_flag.py P-1042 P-1043 P-9999
  python ab_prompt_flag.py --percent 25 P-1 P-2 P-3
"""

from __future__ import annotations

import argparse
import hashlib

import versions


def bucket_for(patient_id: str, percent: int) -> int:
    """Stable 0..99 bucket for a patient id."""
    digest = hashlib.sha256(patient_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def assign_variant(patient_id: str, percent: int = 10) -> dict:
    bucket = bucket_for(patient_id, percent)
    is_candidate = bucket < percent
    return {
        "patient_id": patient_id,
        "bucket": bucket,
        "variant": "candidate" if is_candidate else "control",
        "prompt_version": versions.DEFAULT_PROMPT_VERSION
        if not is_candidate
        else "1.3.0-candidate",
        "rollout_percent": percent,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic A/B prompt assignment")
    parser.add_argument("patient_ids", nargs="+")
    parser.add_argument("--percent", type=int, default=10,
                        help="%% of keys routed to the candidate (default 10)")
    args = parser.parse_args()

    if not 0 <= args.percent <= 100:
        parser.error("--percent must be 0-100")

    counts = {"control": 0, "candidate": 0}
    for pid in args.patient_ids:
        v = assign_variant(pid, args.percent)
        counts[v["variant"]] += 1
        print(f"{pid:>10}  bucket={v['bucket']:>2}  {v['variant']:<9}  "
              f"prompt={v['prompt_version']}")
    total = len(args.patient_ids)
    print(f"\ntotal={total} control={counts['control']} "
          f"candidate={counts['candidate']} "
          f"({counts['candidate'] * 100 // max(total, 1)}% canary)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
