"""Run the money gate over all 12 tickets and print what it decides."""
import json
import sys
from pathlib import Path

# Directly running a script puts only scripts/ on sys.path, not the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.money_gate import run_money_gate
from app.schemas import Ticket

with (PROJECT_ROOT / "data" / "dhaba_tickets.json").open() as f:
    tickets = [Ticket(**t) for t in json.load(f)["tickets"]]

print(f"{'ticket':8} {'refund':7} {'amount':>6}  reason_code")
print("-" * 50)
for t in tickets:
    _, r = run_money_gate(t)
    print(f"{t.id:8} {str(r.refund):7} {r.amount_inr:>6}  {r.reason_code}")