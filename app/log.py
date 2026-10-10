import json
import logging
import sys

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(message)s",   # we print our own JSON lines
)
logger = logging.getLogger("dhaba")

# ONLY these keys may ever enter a log line. No subject, no body,
# no company names, no GSTINs — by construction, not by memory.
ALLOWED_KEYS = {
    "ticket_id", "trace_id", "event", "category", "severity",
    "reason_code", "refund", "amount_inr", "needs_human", "confidence",
    "mode", "degraded", "degrade_reason", "injection_detected",
    "duration_ms", "status", "model",
}


def log_event(event: str, **fields) -> None:
    safe = {k: v for k, v in fields.items() if k in ALLOWED_KEYS}
    logger.info(json.dumps({"event": event, **safe}))