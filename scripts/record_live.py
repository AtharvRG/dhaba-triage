"""Live-mode run over all 12 tickets; saves real model outputs as fixtures."""
import json
import sys
from pathlib import Path

import httpx

# Allow direct execution from the repository root: `python scripts/record_live.py`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas import ClassifierResult

with open("data/dhaba_tickets.json") as f:
    tickets = json.load(f)["tickets"]

recorded = {}
with httpx.Client(base_url="http://localhost:8000", timeout=60) as c:
    for t in tickets:
        r = c.post("/triage", json=t).json()
        print(f"{t['id']:8} -> {r['category']:16} conf={r['confidence']} "
              f"degraded={r['degraded']}")
        # store exactly the classifier-shaped fields the fixtures loader expects
        recorded[t["id"]] = {
            "category": r["category"],
            "severity": r["severity"],
            "confidence": r["confidence"],
            "reply_draft": r["reply_draft"],
            "needs_human_suggestion": r["needs_human"],
        }

# validate every entry before writing — no garbage in the fixtures
for tid, entry in recorded.items():
    ClassifierResult(**entry)

with open("fixtures/fixtures.json", "w", encoding="utf-8") as f:
         json.dump(recorded, f, indent=2, ensure_ascii=False)
print("\nrecorded and validated -> fixtures/fixtures.json")