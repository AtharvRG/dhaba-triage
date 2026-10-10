# DECISIONS

What we chose, why, and what we rejected. Every row is defensible in the
pairing session.

| # | Decision | Why | Rejected alternative |
|---|----------|-----|----------------------|
| 1 | Refunds decided by pure code from billing data; the model never sees a refund field | Ticket text can be manipulated — T-1003 literally tries. Billing records can't be sweet-talked | Model proposes refunds with a sanity check — still one sweet-talk away from losing money |
| 2 | Injection = detect + flag + force needs_human; never obey, never delete the text | Deleting text hides evidence from the human; the classifier still needs the real question underneath | Stripping injection text before the model — loses the audit trail |
| 3 | One retry, then degrade to an honest canned reply | Models often self-correct once; after that, a hallucinated answer is worse than "a human will reply" | Infinite retries — burns tokens and delays the user |
| 4 | Fixture mode is the default | Evaluator burns zero tokens; fixture_miss exercises the same degrade path as live | Live-only — a flaky demo is a dead demo |
| 5 | Idempotency via SQLite keyed on ticket_id, replayed flag in the response | Networks retry, users double-click; "we refunded twice" is unacceptable | In-memory dict — dies on restart, exactly when retries happen |
| 6 | Degraded results are never cached | A cached failure is a permanent failure; the next arrival deserves a fresh attempt | Cache everything — simpler, but locks in the worst answer |
| 7 | Refunds above Rs 999 require a human release | Cheap mistakes automate well; expensive ones deserve a glance. Fired on T-1006 (Rs 1499) in the live run | Full auto on all rule-based refunds |
| 8 | In-flight limiter over a queue under overload | Queueing 50/s of model calls just moves the collapse 30 seconds later; degrading early keeps every reply honest and instant | Bounded queue with timeout — user waits 30s to still get the canned reply |
| 9 | Auto-resolution rate as THE dashboard metric | It moves when anything breaks — model down, injection wave, or confident misclassification | Accuracy % — needs labeled ground truth we don't have |
