# Article 05 — Model Routing and Evidence Validation

Companion source for **Choosing Models for AI Agents: Reasoning, Structured Outputs and Model Routing**.

## Requirements and commands

Python **3.9+**, standard library only.

```bash
python model_router.py
python -m unittest -v
```

## What this is (and is not)

- No LLM API calls. Model responses come from deterministic fixtures in `mock_model()`.
- `AuthorizedFinancialSource.fetch()` checks a simulated account and loads `fixtures/approved_financial_report.json`. That file stands in for a separate approved reporting API or database. It is not a live enterprise data source and not a model answer key.
- `ModelProfile` values (quality approval, p95 latency, context size) are illustrative policy metadata, not benchmarks of any real model.
- `decision_controller()` is a minimal stand-in. It shows where a router failure re-enters Article 04's controller policy; it does not retry, replan or pause.

## Demonstrated outcomes

- Schema error (`q1` as a string) is rejected.
- Schema-valid but incorrect evidence (`q2=902`) is rejected against the separately retrieved report.
- A simulated transient timeout is retried within a bounded attempt limit.
- The eligibility filter (stage, data class, structured support, context size, quality sign-off, assumed p95 limit) runs before any model is invoked.
- An incorrect summary is rejected even though its structured percentage is correct.
- Exhausted candidates, authorization denials and missing policy inputs return an explicit `blocked` state with a `stop_or_escalate` action. Only the router's own `RouterFailure` types (and `PolicyViolation`) are converted; an unexpected `RuntimeError` is a bug and propagates.
- Policy inputs fail closed: a missing or invalid `data_class` or `context_chars` raises `PolicyViolation` instead of defaulting to an approved value.
- `run()` returns an `audit` list of `(stage, model, outcome)` records.
- Application bugs (for example a missing context key) raise instead of being reported as model failures.
- 42 automated tests cover the positive and failure paths.

## Summary and interpretation validation: how it works and its limits

Both model-written text fields (the interpretation `reason` and the summary prose) use the same two layers. Targeted checks (percentages, direction, causal phrases) give readable rejection reasons. The final check is an allowlist: the prose must equal the wording derived from the verified percentage, so phrasing the targeted checks do not anticipate is still rejected.

This is a demonstration, not natural-language fact verification. In production, have the model fill structured slots and let trusted code render the sentence, and use semantic evaluation and human review where the stakes require it.

## Production gaps

Replace the fixture provider with an approved model integration and the source adapter with an authenticated database or API. Add backoff with jitter, timeouts, persisted budgets and controller state, and broader semantic-evidence evaluation.
