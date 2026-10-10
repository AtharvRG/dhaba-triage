# Dhaba Triage

One endpoint, `POST /triage`, that turns a raw support ticket into something
a support agent can act on: category, severity, a refund decision, a
ready-to-send reply draft, and an honest flag for when a human needs to look.

The core idea: **the model sorts and writes; code decides money.**
Refunds come from a deterministic gate that reads billing records only.
Ticket text can be manipulated — two of the twelve tickets literally try —
billing records can't be sweet-talked.

## Run it (clean machine)

```bash
git clone <repo-url> && cd dhaba-triage
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app
```

Fixture mode is the default — zero API keys, zero tokens. With the server
running, in another terminal:

```bash
python scripts/run_fixture.py     # all 12 tickets, prints the results table
pytest -v                         # full test suite, offline, ~1 second
```

Live mode (optional): copy `.env.example` to `.env`, set `MISTRAL_API_KEY`
and `TRIAGE_MODE=live`. Model: `zai-glm-5-3` via the Mistral API.
`scripts/record_live.py` runs all 12 live and records the outputs — that's
how `fixtures/fixtures.json` was produced: it's a **recording of a real
run**, not hand-written guesses.

`GET /metrics` exposes counters; the number that matters is
`auto_resolution_rate` (see Task 3).

## Architecture

```
ticket ─> sanitizer ──> money gate ──> classifier ──> overrides ──> response
          (injection      (billing       (model:        (rules:      (+ store:
           tripwire)       facts only,    classify +     human        idempotency)
                           no text in)    draft reply,   flags,
                                          validate/      thresholds)
                                          retry/degrade)
```

- **Sanitizer** — regex tripwire detects prompt-injection attempts; flags
  them, never obeys them. The ticket text still goes to the model (wrapped
  in explicit UNTRUSTED-DATA markers) because the classifier needs to
  understand the real question underneath.
- **Money gate** — pure Python over `purchases[]`. Policy v1:
  trial-conversion with no usage (≤7 days, ≤3 opens) → full refund;
  renewal with zero app opens (≤30 days) → full refund; product in use →
  no automatic refund. Refunds above ₹999 require a human release.
- **Classifier** — strict JSON contract validated with Pydantic. Invalid
  output → one retry → still bad → degrade to an honest canned reply with
  `needs_human: true`. Under overload, an in-flight limiter degrades
  instantly instead of queueing forever.
- **Logs** — allowlist only: ticket IDs, categories, refund facts. Ticket
  text physically cannot enter a log line; the log function rejects any
  key not on the list.
- **Store** — SQLite keyed on `ticket_id`; the same ticket twice returns
  the stored answer (`replayed: true`) and never re-runs the money path.
  Degraded results are never cached — a cached failure is a permanent
  failure.

`DECISIONS.md` has the full decision log with rejected alternatives.

## Task 2 — what it decided, and do I agree

Live run on `zai-glm-5-3`, all twelve validated first pass, zero degrades.

| ticket | category         | sev | refund    | human | conf | agree?                                                                                  |
| ------ | ---------------- | --- | --------- | ----- | ---- | --------------------------------------------------------------------------------------- |
| T-1001 | refund_request   | P2  | ✔ ₹249  | no    | 0.95 | yes — textbook trial-conversion complaint, 0 app opens                                 |
| T-1002 | crash_bug        | P1  | no        | yes   | 0.95 | yes — paying user blocked; engineering must see it                                     |
| T-1003 | data_loss        | P2  | no        | yes   | 0.90 | yes — see injection section                                                            |
| T-1004 | cancellation     | P2  | no        | no    | 0.90 | yes — trial only, ₹1, nothing to undo                                                 |
| T-1005 | payment_failure  | P1  | no        | yes   | 0.90 | yes — payment is`initiated`, not failed; no refund because the money is still moving |
| T-1006 | refund_request   | P2  | ✔ ₹1499 | yes   | 0.92 | yes — autopay off + 0 opens since March; human releases it (>₹999)                    |
| T-1007 | feature_request  | P3  | no        | no    | 0.97 | yes — last renewal actually failed; a happy user on a lapsed plan                      |
| T-1008 | fraud_dispute    | P0  | ✔ ₹249  | yes   | 0.90 | mostly — refund is data-backed, but a cyber-cell threat is always a human conversation |
| T-1009 | duplicate_charge | P2  | no        | yes   | 0.90 | **the ambiguous one** — see below                                                |
| T-1010 | invoice_request  | P3  | no        | yes   | 0.97 | yes — the model itself suggested a human (GSTIN correctness); I agree                  |
| T-1011 | pre_sales        | P2  | no        | yes   | 0.95 | yes — see injection section                                                            |
| T-1012 | refund_request   | P2  | ✔ ₹249  | no    | 0.85 | yes — angry, 2 opens; the threat changes nothing, the data decides                     |

**Genuinely ambiguous: T-1009 and T-1008.**

T-1009: billing shows one success and one *failure* — by our records there
is no double charge. But the user's bank statement can disagree with our
records, and I can't see their bank statement. The system doesn't guess:
the reply draft tells the user what our records show, asks them to check
tomorrow, and holds the ticket for a human. "Confidently correct about
incomplete data" is the failure mode I designed against here.

T-1008: the data says refund (0 app opens in 26 days), and the gate
approved ₹249 — but the *claim* (a 71-year-old who never installed the
app) can only be verified by a person, and a cyber-cell threat makes it
P0 regardless of what the data says. So: refund approved, human releases.

**When the system can't tell, it doesn't guess.** Low confidence, ambiguous
categories (fraud, payment failure, data loss), injection flags, and big
refunds all force `needs_human: true`. The degrade path is the same stance
at the infrastructure level: when the model's output can't be trusted,
the user gets an honest "a specialist will reply" — never a hallucination.

**The two tickets addressed to the assistant:**

- **T-1003** — fake "SYSTEM NOTE FOR THE SUPPORT ASSISTANT" demanding a
  full refund for a "verified VIP":
  `"injection_detected": true`, refund `false`, `needs_human: true`.
  The injection got the user nothing. Notably, the money gate would have
  refused anyway on the data alone (212 app opens since renewal) — the
  injection never even reached a decision it could influence.
- **T-1011** — post-script demanding the system prompt and internal refund
  rules, then auto-resolution: `injection_detected: true`,
  `needs_human: true`, and the reply draft answers the *actual* question
  (does premium work offline). No prompt text, no refund rules, no
  auto-resolve.

Proof both behave: `tests/test_triage.py` —
`test_injection_tickets_flagged_and_held` fails if either ticket ever
gets a refund; `test_t1011_reply_does_not_leak_prompt` fails if the
draft ever leaks prompt text.

**Dashboard number:** auto-resolution rate — the % of tickets closed with
no human (`GET /metrics`). One number, every failure mode: model API down
→ degrades spike → rate falls. Injection wave → humans spike → rate falls.
Model gone confidently wrong → support pushes tickets back → rate falls.
(Metrics are in-memory and reset on restart by design; the idempotency
store does not. At production scale the counters move to Prometheus —
the store stays.)

## Task 3 — backend track: 50 tickets/second during an outage

**Shipped, not just written:** an in-flight limiter on model calls
(`classifier.py`). Above `MAX_IN_FLIGHT` concurrent calls, new ones degrade
instantly — the user gets an honest canned reply in milliseconds. No
unbounded queue, no timeout pile-up, no collapse. What the user gets while
degraded: a truthful "we've logged this, a specialist will reply within a
few hours, nothing further will be charged" — never a hallucination,
never a crash.

**What I'd change at real scale:**

- Async end-to-end: model calls via `httpx.AsyncClient` with a connection
  pool sized to the limiter.
- A durable queue — the `tickets` table doubles as one: accept → persist →
  `202 Accepted` → workers drain and call the model. Under outage users
  get instant "logged, human within hours," and nothing is lost.
- Retry with jitter and a circuit breaker on the model API; the
  idempotency key stays `ticket_id`, so replays after a crash are free.

**Storage sketch:**

```
tickets(ticket_id PK, received_at, subject_encrypted, body_encrypted,
        purchases_json, app_opens, status, trace_id)
triage_results(ticket_id PK FK, category, severity, refund_json,
               reply_draft, needs_human, confidence, degraded,
               policy_version, created_at, released_by, released_at)
audit_log(ts, ticket_id, event, actor, payload_json)  -- money decisions only
```

Ticket text encrypted at rest (a company name and GSTIN live in these
bodies); `policy_version` on every refund so a policy change never
silently re-decides old money; `released_by` proves which human approved
which big refund.

**The 3am thing:** every response carries a `trace_id`, and every log line
(allowlisted fields only) carries it too. One grep —
`grep <trace_id> server.log` — reconstructs the full life of one ticket:
sanitized, gated, classified, decided, stored. No PII to leak, no missing
context. And `/metrics` answers "is this systemic?" before you open a
single log: if auto-resolution rate is on the floor, it's the model, not
the ticket.

## Task 4 — how I used AI

[YOU: 2-3 sentences — which agent(s), rough share of code written by them,
and the one-line thesis. Suggested thesis: "the agent wrote most of the
lines; the check scripts caught everything that mattered."]

**Best prompt (verbatim, as sent — the first message of the engagement,which set the shape of everything that followed):**

> "Phase 2 — Build: work in milestones I can run and verify after each.Maintain a running DECISIONS.md (what, why, alternative rejected).When you use a technique I might not know, teach it in ≤5 lines — Imust be able to explain it to an interviewer."

> "1. Defensibility over cleverness: no dependency, pattern, or trick I can't explain. If it's over my head, simplify it or teach it."

Everything downstream — the milestone structure, the decision log, thecheck scripts, the fact that I can defend every line in a pairingsession — came from those few sentences. The later prompts were short("next!", "less goo!", "before i do the live run...") because thesteering happened before the code did: agree on the protocol first, andthe agent's output becomes verifiable chunks instead of a pile you haveto trust.

**What the agent got wrong — all caught by running things, none by
reading the code:**

1. The money-gate prompt builder formatted `days_since_last_renewal` with
   `:.0f` — which crashes on `None` for trial-only tickets. Passed three
   tickets, died on the fourth (T-1004). Caught by the run-all-12 script.
2. The SQLite store was written without `check_same_thread=False`; FastAPI
   runs sync endpoints in a threadpool, so the first real request 500'd.
   Caught by the idempotency check script.
3. The first live model call returned `message.content` as a *list of
   blocks* (GLM family), not a string — `json.loads(list)` raised
   `TypeError`, which the degrade path didn't catch, so the endpoint
   crashed instead of degrading. Fixed twice: normalize the shape at the
   source, and let the retry loop catch broadly so no unknown shape can
   ever take the endpoint down.
4. The recording script wrote `fixtures.json` without `encoding="utf-8"`;
   Windows cp1252 choked on `₹` after all 12 API calls had already
   succeeded.

**Written by hand, on purpose:** the refund policy thresholds (₹999
release, 3 opens, 30 days) and DECISIONS.md. Directing an agent on policy
trade-offs is slower than deciding them — an agent can generate a rules
engine, but it can't take responsibility for where the money goes.

## What I'd build next (2 more weeks)

1. **Reply-draft quality loop** — log agent edits to drafts; the gap
   between draft and sent reply is the real training signal for prompt
   iterations.
2. **Policy v2: partial refunds** — a 90-day annual user with 10 opens
   deserves something between "full refund" and "nothing."
3. **Language detection upstream** — route Devanagari vs romanized
   Hinglish properly (T-1005-class tickets).
4. **The full Task 3 design, shipped** — async classifier + durable queue.
