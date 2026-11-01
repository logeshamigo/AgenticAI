# Article 06 — Executable Companion v2

## Run (Python 3.10+; tested on Python 3.13.5)

```bash
python -m unittest -v
python agent_tools.py
```

The first command runs **25 automated tests** (including ten concurrent SQLite attempts against a single logical operation). The second creates a **new temporary SQLite database on every run** and simulates a committed write whose response is lost.

Expected demo output:

```text
read: ok; attempts=2
revenue: 1000 to 920 USD thousands (-8.0%)
review without approval: blocked
first approved write (committed, response lost): uncertain
retry SAME step: {'ticket_id': 'TKT-181DFC1D05640FD5', 'created': False}
stored tickets: 1
```

## Files

- `agent_tools.py` — trusted-context dispatcher, strict local argument parser, source normalization, step/payload approvals, workflow budgets, SQLite-backed idempotency, and a post-commit lost-response injector.
- `test_agent_tools.py` — unit/integration suite for contracts, security boundaries, recovery, and concurrency.

## Scope and limitations

This is a **local deterministic application-side tool execution** demonstration; it deliberately does not make LLM API calls. The `sample_context(approved=True)` option fabricates a prior approval for tests only, not an end-user approval UI. All data are fabricated. The provenance envelope reduces exposure but does not prevent all prompt injection. Workflow budgets are in-memory for the demo and require durable shared enforcement in production. SQLite constraints protect local rows, not effects performed in external APIs. Ticket IDs are illustrative and uniqueness-enforced locally, not a production ID generation strategy.

## References

- OpenAI function calling: https://developers.openai.com/api/docs/guides/function-calling
- Anthropic tool use: https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview
- AWS agent idempotency (AGENTREL06-BP04): https://docs.aws.amazon.com/wellarchitected/latest/agentic-ai-lens/agentrel06-bp04.html
- Microsoft transient fault handling: https://learn.microsoft.com/en-us/azure/architecture/best-practices/transient-faults
- OWASP Agentic AI AAI7: https://cornucopia.owasp.org/cards/AAI7
