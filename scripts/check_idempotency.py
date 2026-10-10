"""Post T-1001 twice. Second response must be the stored one (replayed=True),
same trace_id, and the log must show triage_replayed, not a fresh refund run."""
import json

import httpx

with open("data/dhaba_tickets.json") as f:
    t = json.load(f)["tickets"][0]

with httpx.Client(base_url="http://localhost:8000") as c:
    first = c.post("/triage", json=t).json()
    second = c.post("/triage", json=t).json()

print("first  trace:", first["trace_id"], "| replayed:", first["replayed"])
print("second trace:", second["trace_id"], "| replayed:", second["replayed"])
assert first["trace_id"] == second["trace_id"], "different trace ids!"
assert second["replayed"] is True, "second call was not served from store!"
print("\nIDEMPOTENT ✓ — same answer, same trace, no second refund decision.")