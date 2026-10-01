#!/usr/bin/env python3
"""mcp_dashboard_sketch.py - Thursday Lab 2: ASCII dashboard for tool health.

Renders the tool_metrics store as a terminal dashboard: per-tool call
counts, error rates against the 0.10 gate, and a GO/NO-GO banner the
clinical_ops brief references. No web server, no dependency - it is a
sketch of what the Week 9+ Grafana panel would show, not the real one.

Usage:
  python mcp_dashboard_sketch.py            # seeded demo data
  python mcp_dashboard_sketch.py --json     # machine-readable snapshot
"""

from __future__ import annotations

import argparse
import json

import tool_metrics
from tool_metrics import STORE


def _seed_demo() -> None:
    """Seed with a plausible morning of staging traffic."""
    demo = [
        ("find_clinic_by_county", True, 11),
        ("find_clinic_by_county", True, 9),
        ("find_clinic_by_county", True, 14),
        ("find_clinic_by_county", False, 12),
        ("plan_delivery_route", True, 38),
        ("plan_delivery_route", True, 41),
        ("plan_delivery_route", False, 33),
    ]
    for tool, ok, ms in demo:
        STORE.record(tool, ok, ms)


def render(snapshot: dict, gate: float = 0.10) -> str:
    width = 62
    lines = ["=" * width]
    lines.append("AfyaPlus MCP tool health - staging (sketch)".center(width))
    lines.append("=" * width)
    lines.append(f"{'tool':<26}{'calls':>6}{'errors':>8}{'err_rate':>10}  bar")
    lines.append("-" * width)
    for tool, s in snapshot.items():
        rate = s["error_rate"]
        filled = int(rate / gate * 20) if gate else 0
        bar = "#" * min(filled, 20) + "." * max(20 - filled, 0)
        flag = " <-- OVER GATE" if rate > gate else ""
        lines.append(
            f"{tool:<26}{s['calls']:>6}{s['errors']:>8}{rate:>10.2%}  {bar}{flag}"
        )
    lines.append("-" * width)
    total = tool_metrics.STORE.total_error_rate()
    verdict = "GO" if total <= gate else "NO-GO"
    lines.append(f"aggregate error_rate = {total:.2%}  (gate {gate:.0%})  ->  {verdict}")
    lines.append("=" * width)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP tool health dashboard sketch")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of ASCII")
    args = parser.parse_args()

    _seed_demo()
    snapshot = STORE.snapshot()
    if args.json:
        print(json.dumps({
            "gate": 0.10,
            "total_error_rate": tool_metrics.STORE.total_error_rate(),
            "tools": snapshot,
        }, indent=2))
    else:
        print(render(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
