from datetime import timedelta

from app.schemas import BillingFacts, RefundDecision, Ticket

# ---- Policy v1: constants, not vibes ----
TRIAL_TO_RENEWAL_WINDOW = timedelta(hours=72)   # trial then renewal within 3 days = conversion
TRIAL_CONV_MAX_AGE = timedelta(days=7)          # complaint came soon after conversion
TRIAL_CONV_MAX_OPENS = 3                        # barely opened the app since paying
ZERO_USAGE_MAX_AGE = timedelta(days=30)         # charged but never opened the app since

POLICY_VERSION = "v1"


def build_facts(ticket: Ticket) -> BillingFacts:
    successful = [p for p in ticket.purchases if p.status == "successful" and p.type == "renewal"]
    trials = [p for p in ticket.purchases if p.status == "successful" and p.type == "trial"]

    last_renewal = max(successful, key=lambda p: p.at) if successful else None

    is_conversion = False
    if last_renewal and trials:
        latest_trial = max(trials, key=lambda p: p.at)
        gap = last_renewal.at - latest_trial.at
        is_conversion = timedelta(0) < gap <= TRIAL_TO_RENEWAL_WINDOW

    days_since = None
    if last_renewal:
        days_since = (ticket.received_at - last_renewal.at).total_seconds() / 86400

    return BillingFacts(
        has_successful_renewal=bool(successful),
        last_renewal_amount=last_renewal.amount_inr if last_renewal else 0,
        last_renewal_at=last_renewal.at if last_renewal else None,
        days_since_last_renewal=days_since,
        app_opens_since_renewal=ticket.app_opens_since_renewal,
        is_trial_conversion=is_conversion,
        successful_renewal_count=len(successful),
        has_pending_payment=any(p.status == "initiated" for p in ticket.purchases),
        has_recent_failure=any(p.status == "failed" for p in ticket.purchases),
    )


def decide_refund(facts: BillingFacts) -> RefundDecision:
    # R0: nothing successfully charged → nothing to refund.
    if not facts.has_successful_renewal:
        return RefundDecision(
            refund=False, reason_code="no_successful_charge",
            rationale="No successful renewal payment on record; nothing to refund.",
            policy_version=POLICY_VERSION,
        )

    age = timedelta(days=facts.days_since_last_renewal or 0)

    # R1: trial→renewal conversion, complained within a week, barely used.
    if (facts.is_trial_conversion
            and age <= TRIAL_CONV_MAX_AGE
            and facts.app_opens_since_renewal <= TRIAL_CONV_MAX_OPENS):
        return RefundDecision(
            refund=True, amount_inr=facts.last_renewal_amount,
            reason_code="trial_conversion_unused",
            rationale=(
                f"₹{facts.last_renewal_amount} charged ~24h after a ₹1 trial "
                f"(auto-conversion), only {facts.app_opens_since_renewal} app "
                f"opens since. Policy: full refund."
            ),
            policy_version=POLICY_VERSION,
        )

    # R2: charged but the app was never opened since the renewal.
    if facts.app_opens_since_renewal == 0 and age <= ZERO_USAGE_MAX_AGE:
        return RefundDecision(
            refund=True, amount_inr=facts.last_renewal_amount,
            reason_code="renewal_zero_usage",
            rationale=(
                f"₹{facts.last_renewal_amount} renewal with zero app opens since "
                f"({facts.days_since_last_renewal:.0f} days ago). Policy: full refund."
            ),
            policy_version=POLICY_VERSION,
        )

    # R3: they used the product after paying. No automatic refund.
    return RefundDecision(
        refund=False, reason_code="usage_after_renewal",
        rationale=(
            f"{facts.app_opens_since_renewal} app opens since the last renewal — "
            f"product was in use. No automatic refund; human may use judgement."
        ),
        policy_version=POLICY_VERSION,
    )


def run_money_gate(ticket: Ticket) -> tuple[BillingFacts, RefundDecision]:
    facts = build_facts(ticket)
    return facts, decide_refund(facts)