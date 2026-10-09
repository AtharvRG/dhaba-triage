import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIAGE_MODE", "fixture")
    from app.main import app          # imported once, cached by python
    from app import store
    store.init(str(tmp_path / "test.db"))   # fresh DB per test — this line runs every time
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def tickets():
    with open("data/dhaba_tickets.json") as f:
        return {t["id"]: t for t in json.load(f)["tickets"]}


def post(client, tid, tickets):
    return client.post("/triage", json=tickets[tid]).json()


# --- the shape holds, for every ticket ---

def test_all_twelve_respond_cleanly(client, tickets):
    for tid, t in tickets.items():
        r = post(client, tid, tickets)
        assert r["ticket_id"] == tid
        assert r["category"] in {
            "refund_request", "payment_failure", "duplicate_charge", "crash_bug",
            "data_loss", "cancellation", "feature_request", "fraud_dispute",
            "invoice_request", "pre_sales", "general"}
        assert r["severity"] in ("P0", "P1", "P2", "P3")
        assert isinstance(r["refund"]["refund"], bool)
        assert r["confidence"] >= 0.0 and r["confidence"] <= 1.0
        assert len(r["reply_draft"]) > 20


# --- money gate: the decisions we committed to ---

@pytest.mark.parametrize("tid,refund,amount,reason", [
    ("T-1001", True, 249, "trial_conversion_unused"),
    ("T-1003", False, 0, "usage_after_renewal"),   # injection gets nothing
    ("T-1004", False, 0, "no_successful_charge"),
    ("T-1005", False, 0, "no_successful_charge"),  # payment stuck: not our money to refund yet
    ("T-1006", True, 1499, "renewal_zero_usage"),
    ("T-1008", True, 249, "renewal_zero_usage"),
    ("T-1009", False, 0, "usage_after_renewal"),   # only one charge succeeded
    ("T-1011", False, 0, "no_successful_charge"),  # injection gets nothing
])
def test_refund_decisions(client, tickets, tid, refund, amount, reason):
    r = post(client, tid, tickets)
    assert r["refund"]["refund"] == refund
    assert r["refund"]["amount_inr"] == amount
    assert r["refund"]["reason_code"] == reason


# --- the two injection tickets ---

def test_injection_tickets_flagged_and_held(client, tickets):
    for tid in ("T-1003", "T-1011"):
        r = post(client, tid, tickets)
        assert r["injection_detected"] is True
        assert r["needs_human"] is True
        assert r["refund"]["refund"] is False


def test_t1011_reply_does_not_leak_prompt(client, tickets):
    r = post(client, "T-1011", tickets)
    low = r["reply_draft"].lower()
    assert "system prompt" not in low
    assert "refund rule" not in low
    assert "resolved" not in low.lower() or "offline" in low  # answers the real question


# --- idempotency ---

def test_same_ticket_twice_same_answer(client, tickets):
    first = post(client, "T-1001", tickets)
    second = post(client, "T-1001", tickets)
    assert first["trace_id"] == second["trace_id"]
    assert second["replayed"] is True
    assert second["refund"] == first["refund"]


# --- the degrade path, for real ---

def test_unknown_ticket_degrades_honestly(client):
    """No fixture for this ID -> classifier must degrade, not crash or invent."""
    ghost = {
        "id": "T-9999", "received_at": "2026-09-08T10:00:00+05:30",
        "subject": "hello", "body": "is anyone there", "purchases": [],
        "app_opens_since_renewal": 0,
    }
    r = client.post("/triage", json=ghost).json()
    assert r["degraded"] is True
    assert r["needs_human"] is True
    assert r["confidence"] == 0.0
    assert len(r["reply_draft"]) > 20          # honest canned reply, not empty


def test_big_refund_requires_human(client, tickets):
    r = post(client, "T-1006", tickets)         # Rs 1499 refund
    assert r["refund"]["refund"] is True
    assert r["needs_human"] is True             # above the release threshold