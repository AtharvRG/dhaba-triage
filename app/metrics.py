"""In-memory counters. The dashboard number: auto-resolution rate —
% of tickets fully handled with no human. If this drops, the service
is either degrading or over-escalating, and both need eyes."""
from collections import Counter

counters = Counter()

def record(event: str) -> None:
    counters[event] += 1

def snapshot() -> dict:
    total = counters["triage_total"]
    return {
        "triage_total": total,
        "auto_resolved": counters["auto_resolved"],
        "needs_human": counters["needs_human"],
        "replayed": counters["replayed"],
        "degraded": counters["degraded"],
        "auto_resolution_rate": (
            round(counters["auto_resolved"] / total, 3) if total else None
        ),
    }