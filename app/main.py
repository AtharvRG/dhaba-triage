import time
import uuid

from fastapi import FastAPI

from app import store, metrics
from app.classifier import classify, needs_human_final
from app.config import settings
from app.log import log_event
from app.money_gate import run_money_gate
from app.sanitizer import sanitize
from app.schemas import Ticket, TriageResponse

app = FastAPI(title="Dhaba Triage")
store.init(settings.db_path)

@app.get("/healthz")
def health():
    return {"ok": True, "mode": settings.triage_mode}


@app.post("/triage")
def triage(ticket: Ticket) -> TriageResponse:
    cached = store.get(ticket.id)
    if cached is not None:
        log_event(
            "triage_replayed",
            ticket_id=ticket.id,
            trace_id=cached.trace_id,
            mode=settings.triage_mode,
            refund=cached.refund.refund,
            amount_inr=cached.refund.amount_inr,
        )
        response = cached
    else:
        trace_id = uuid.uuid4().hex[:12]
        started = time.monotonic()

        report = sanitize(ticket)                    # 1. tripwire first
        facts, refund = run_money_gate(ticket)       # 2. money — never the model
        result = classify(ticket, facts, refund, report)  # 3. classify + draft
        human = needs_human_final(result, report, refund)  # 4. rules decide the human flag

        response = TriageResponse(
            ticket_id=ticket.id,
            category=result.category,
            severity=result.severity,
            refund=refund,
            reply_draft=result.reply_draft,
            needs_human=human,
            confidence=result.confidence,
            degraded=result.degraded,
            degrade_reason=result.degrade_reason,
            injection_detected=report.injection_detected,
            trace_id=trace_id,
        )

        # NOTE: only allowlisted fields. No subject, no body, ever.
        log_event(
            "triage_complete",
            ticket_id=ticket.id, trace_id=trace_id,
            category=result.category.value, severity=result.severity.value,
            refund=refund.refund, amount_inr=refund.amount_inr,
            reason_code=refund.reason_code,
            needs_human=human, confidence=result.confidence,
            injection_detected=report.injection_detected,
            degraded=result.degraded, mode=settings.triage_mode,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        store.put(ticket.id, response)

    metrics.record("triage_total")
    if cached is not None:
        metrics.record("replayed")
    if response.degraded:
        metrics.record("degraded")
    if not response.needs_human:
        metrics.record("auto_resolved")
    else:
        metrics.record("needs_human")
    return response


@app.get("/metrics")
def get_metrics():
    return metrics.snapshot()