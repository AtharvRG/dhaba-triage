import uuid

from fastapi import FastAPI

from app.config import settings
from app.money_gate import run_money_gate
from app.schemas import Category, Severity, Ticket, TriageResponse

app = FastAPI(title="Dhaba Triage")


@app.get("/healthz")
def health():
    return {"ok": True, "mode": settings.triage_mode}


@app.post("/triage")
def triage(ticket: Ticket) -> TriageResponse:
    """Money gate runs first, always. AI fields are placeholders until M2."""
    facts, refund = run_money_gate(ticket)
    return TriageResponse(
        ticket_id=ticket.id,
        category=Category.GENERAL,      # placeholder — M2 replaces
        severity=Severity.P2,           # placeholder — M2 replaces
        refund=refund,                  # REAL — never comes from the model
        needs_human=True,               # safe default while AI part is stubbed
        confidence=0.0,
        trace_id=uuid.uuid4().hex[:12],
    )