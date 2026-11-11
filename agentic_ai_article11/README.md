# Article 11 — Human-in-the-Loop AI Agents (Reference Code)

Python 3.10+ · standard library + SQLite. No LLM, external API, login, browser or model key needed.

## Quick start

From the extracted project folder:

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

**Verified:** `31 tests ... OK`. The demo prints:

```text
Proposal: pending
Execute before review: pending
Review: approved
Execute after review: verified
Final ticket: {'ticket_id': 'T-104', 'tenant': 'acme', 'status': 'Resolved', 'version': 2}
Writes: 1
Audit: ['proposed', 'approved', 'executed']
```

## Approval and execution behavior

- `propose()` checks the action allowlist and ticket tenant, writes the bounded request and its expiry, **not** the ticket update.
- `review()` accepts a pending proposal only from an authorized, tenant-scoped reviewer who is not the requester.
- `execute()` checks expiry even for pending requests; otherwise pending/rejected/stale/blocked cannot execute. It rechecks the action and reviewer scope after approval. A changed policy or revoked reviewer access produces a terminal `blocked` state.
- It compares the approved action fingerprint and the ticket resource version before execution; version mismatch results in `stale`.
- Approved execution commits a local ticket change and unique effect record within one SQLite `BEGIN IMMEDIATE` transaction and confirms the local ticket state.
- `expire_requests(now)` sweeps overdue `pending` **and** `approved` requests, persisting `expired` and recording a single audit event. It is **not a background worker**. A production service must run it periodically from a trusted scheduler, and derive `now` from a trusted clock.
- Lost-response-after-commit simulation and concurrent execution tests show one committed **local** effect; they do not establish distributed exactly-once delivery.

## Test coverage (31 cases)

Approval/rejection; reviewer/tenant permissions; separation of duties; pending/approved expiry; expiry sweeps and repeat sweeps after restart; action-time revalidation; reviewer permission revocation; tampered approver identity; terminal blocked state; tampered payload detection; stale target; one-time local execution; concurrency; durable state after restart; post-commit lost response; audit history; invalid requests and policy denials.

## Security and correctness boundaries

This is a local control-flow demonstration, not production authorization. The code trusts caller-supplied `now`, `requester`, `reviewer` and in-memory reviewer scopes; a real application must derive these from authenticated server-side identity and trusted time, protect the approval store, and enforce resource-level policy. SHA-256 digests detect accidental modification in this trusted demo but are **not cryptographically sealed authorizations**: anyone allowed to alter the stored payload and digest can forge a matching pair.

Real external side effects require destination-supported idempotency and authoritative reconciliation or escalation. SQLite atomicity does not extend to external APIs, browser writes, payments or email.


## Files

```text
hitl.py                  ApprovalController; SQLite workflow and expiry sweep
demo.py                  End-to-end demonstration
tests/test_hitl.py       31 automated tests
README.md               Setup, behavior and explicit limitations
```
