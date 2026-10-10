"""Run all 12 tickets through /triage in fixture mode, print the table."""
import json

import httpx

with open("data/dhaba_tickets.json") as f:
    tickets = json.load(f)["tickets"]

print(f"{'ticket':8} {'category':16} {'sev':3} {'refund':>6} {'human':5} {'conf':4} {'inj':3}")
print("-" * 60)
with httpx.Client(base_url="http://localhost:8000") as c:
    for t in tickets:
        r = c.post("/triage", json=t).json()
        print(f"{r['ticket_id']:8} {r['category']:16} {r['severity']:3} "
              f"{str(r['refund']['refund'])[:1] + '/' + str(r['refund']['amount_inr']):>6} "
              f"{str(r['needs_human'])[:1]:5} {r['confidence']:<4.2f} "
              f"{'!!' if r['injection_detected'] else ''}")