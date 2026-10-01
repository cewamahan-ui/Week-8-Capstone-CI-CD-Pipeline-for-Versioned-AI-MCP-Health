"""tool_metrics.py - Thursday: the shared counter store for MCP tool calls.

A tiny thread-safe in-process metrics registry that both the MCP
server wrappers and the API layer can import. The capstone dashboard
(mcp_dashboard_sketch.py) and the CI error-rate gate both read from
the same counters, so one number - error_rate - is the single source
of truth for the go/no-go rule in the change brief.

Shape kept deliberately simple: counters and histograms of ints, no
external dependency, swap-in point for Prometheus/OTel noted below.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class ToolStat:
    calls: int = 0
    errors: int = 0
    latency_ms_total: int = 0
    last_error: str | None = None
    last_called_at: float | None = None

    @property
    def avg_latency_ms(self) -> float:
        return round(self.latency_ms_total / self.calls, 1) if self.calls else 0.0


@dataclass
class MetricsStore:
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _stats: dict[str, ToolStat] = field(default_factory=dict)

    def record(self, tool: str, ok: bool, latency_ms: int = 0,
               error: str | None = None) -> None:
        with self._lock:
            stat = self._stats.setdefault(tool, ToolStat())
            stat.calls += 1
            stat.latency_ms_total += max(0, latency_ms)
            stat.last_called_at = time.time()
            if not ok:
                stat.errors += 1
                stat.last_error = error or "unspecified"

    def snapshot(self) -> dict:
        with self._lock:
            return {
                tool: {
                    "calls": s.calls,
                    "errors": s.errors,
                    "error_rate": round(s.errors / s.calls, 4) if s.calls else 0.0,
                    "avg_latency_ms": s.avg_latency_ms,
                    "last_error": s.last_error,
                }
                for tool, s in sorted(self._stats.items())
            }

    def error_rate(self, tool: str) -> float:
        with self._lock:
            s = self._stats.get(tool)
            return round(s.errors / s.calls, 4) if s and s.calls else 0.0

    def total_error_rate(self) -> float:
        """Aggregate error rate across all tools - the go/no-go number."""
        with self._lock:
            calls = sum(s.calls for s in self._stats.values())
            errors = sum(s.errors for s in self._stats.values())
            return round(errors / calls, 4) if calls else 0.0


# Process-wide singleton.
STORE = MetricsStore()


def record(tool: str, ok: bool, latency_ms: int = 0, error: str | None = None) -> None:
    """Module-level convenience so callers do not import the class."""
    STORE.record(tool, ok, latency_ms, error)


if __name__ == "__main__":
    # Demo: a healthy tool, a flaky one, and the go/no-go read-out.
    record("find_clinic_by_county", ok=True, latency_ms=12)
    record("find_clinic_by_county", ok=True, latency_ms=8)
    record("plan_delivery_route", ok=True, latency_ms=40)
    record("plan_delivery_route", ok=False, latency_ms=35, error="unknown origin 'nairabi'")
    print(f"error_rate(total)={STORE.total_error_rate()}  (gate: 0.10)")
    for tool, s in STORE.snapshot().items():
        print(f"  {tool:<24} calls={s['calls']:<3} errors={s['errors']:<2} "
              f"avg_ms={s['avg_latency_ms']}")
