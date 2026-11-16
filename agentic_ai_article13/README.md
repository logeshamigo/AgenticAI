# Article 13 — MCP vs A2A: Boundary Enforcement Teaching Demo v2.0

Deterministic Python standard-library demonstration of **application-side controls** around MCP-style capability access and A2A-style task delegation.

**Not a networked MCP client/server or A2A client/server.** There are no actual protocol transports, models, OAuth flows, persistence, external task queries, automated retries, or distributed orchestration.

## Run from ZIP root

```bash
cd agentic_ai_article13
python3 protocol_boundary.py
python3 -m unittest discover -s tests -v
```

## What the 25 tests cover

* MCP-style capability permission and tenant matching, verified evidence and source checks.
* A2A-style delegation admission: principal, tenant, approved target, `delegate:analysis` permission, and `max_calls >= 1` admission threshold.
* Caller-supplied **completed task IDs** return `DUPLICATE_TASK` (never a contradictory-evidence `CONFLICT`).
* Caller-supplied **unresolved task IDs** return `OUTCOME_UNKNOWN` with a reconcile-before-retry instruction, rather than authorizing redispatch.
* Confirmed execution errors produce `FAILED`; ambiguous missing acknowledgments and timeouts produce `OUTCOME_UNKNOWN`.
* Whitespace-only subjects, empty tenants, empty evidence sources are rejected.
* `compare_findings` uses a deterministic numeric contradiction fixture to demonstrate `CONFLICT`, not real evidence reasoning.

## Outcome semantics

* `AUTHORIZED`: delegation policy gate passed; **no delegated work was executed**.
* `COMPLETED`: a trusted fixture result was accepted / numeric fixture agreed; not evidence of live protocol completion.
* `BLOCKED`: identity, tenant, permission, destination, or admission policy failed.
* `FAILED`: caller explicitly supplied a known execution error.
* `OUTCOME_UNKNOWN`: execution state is ambiguous or task ID is caller-marked unresolved; reconcile externally before retry.
* `DUPLICATE_TASK`: caller identifies a previously completed task ID; do not re-execute.
* `INSUFFICIENT_EVIDENCE`: evidence missing/unverified or acknowledgment alone is insufficient.
* `CONFLICT`: contradictory values from two named fixture sources.

## Deliberate limitations

* `max_calls` is **only** a minimum admission condition (`>=1`); it is not decremented or enforced over time. No scope field or scope-restriction engine is present.
* `completed_ids` and `unresolved_ids` are caller-provided immutable sets. The demo neither records nor retrieves task state; **persistence and reconciliation are outside the demo**.
* The transport classifier does not record an outcome into those sets. In a live system, a durable controller must persist uncertainty and reconcile using a remote identifier before allowing a retry.
* This is not protocol conformance, security penetration testing, or evidence of production correctness.

## Official specifications

* MCP 2026-07-28: https://modelcontextprotocol.io/specification/2026-07-28
* A2A v1.0.0: https://a2a-protocol.org/latest/specification/
* A2A Agent Discovery (§8): https://a2a-protocol.org/latest/specification/#8-agent-discovery-the-agent-card
