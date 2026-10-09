from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# --- Input: exactly what's in dhaba_tickets.json ---

class Purchase(BaseModel):
    id: str
    type: Literal["trial", "renewal"]
    amount_inr: int
    status: Literal["successful", "failed", "initiated"]
    at: datetime


class Ticket(BaseModel):
    id: str
    received_at: datetime
    subject: str
    body: str
    purchases: list[Purchase] = Field(default_factory=list)
    app_opens_since_renewal: int = 0


# --- Output: what POST /triage returns ---

class Category(str, Enum):
    REFUND_REQUEST = "refund_request"
    PAYMENT_FAILURE = "payment_failure"      # paid but plan not active
    DUPLICATE_CHARGE = "duplicate_charge"
    CRASH_BUG = "crash_bug"
    DATA_LOSS = "data_loss"
    CANCELLATION = "cancellation"
    FEATURE_REQUEST = "feature_request"
    FRAUD_DISPUTE = "fraud_dispute"
    INVOICE_REQUEST = "invoice_request"
    PRE_SALES = "pre_sales"
    GENERAL = "general"


class Severity(str, Enum):
    # Documented scale (goes in README):
    # P0 = act now: legal/cyber-cell threats, fraud claims, outage-level bugs
    # P1 = paying user blocked from using the product
    # P2 = normal support, answer within a day
    # P3 = nice-to-have: feature requests, paperwork
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class RefundDecision(BaseModel):
    """Written ONLY by the money gate. The model never touches this."""
    refund: bool
    amount_inr: int = 0
    reason_code: str          # machine-readable, e.g. 'trial_conversion_unused'
    rationale: str            # human-readable, for the support agent
    policy_version: str = "v1"


class TriageResponse(BaseModel):
    ticket_id: str
    category: Category
    severity: Severity
    refund: RefundDecision
    reply_draft: str | None = None
    needs_human: bool = False
    confidence: float = 0.0
    degraded: bool = False    # True when we fell back (bad model output etc.)
    trace_id: str = ""        # ties logs together without leaking content

class BillingFacts(BaseModel):
    """Deterministic facts extracted from purchases[] — no opinions here."""
    has_successful_renewal: bool
    last_renewal_amount: int = 0
    last_renewal_at: datetime | None = None
    days_since_last_renewal: float | None = None
    app_opens_since_renewal: int = 0
    is_trial_conversion: bool = False        # ₹1 trial then auto-renewal ~24h later
    successful_renewal_count: int = 0
    has_pending_payment: bool = False        # status == 'initiated' (T-1005)
    has_recent_failure: bool = False         # a failed renewal exists