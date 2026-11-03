# Article 08 — Context Engineering for AI Agents (v5.0)

Author: Logesh Kumaraguru · Python 3.10+ · Standard library only · no API key

## Run from the extracted project root

```bash
python3 example.py
python3 -m unittest discover -s tests -v
```

The runnable output is saved in `EXAMPLE_OUTPUT.txt`, and the test run in `TEST_RESULTS.txt`.
The 52 tests include exclusion-ID leakage regressions and required-period coverage.

## Package layout

- `src/context_engineering/builder.py` — deterministic context builder and renderer
- `src/context_engineering/__init__.py` — public API exports
- `example.py` — reproducible FY2026 vs FY2025 example
- `tests/test_builder.py` — 52 automated tests

## API

- `Evidence`: source ID, tenant, **covered period**, version, update timestamp, upstream `verified` flag, relevance, token estimate, text, optional `claim_key` and `superseded` flag.
- `ContextPolicy`: scoped tenant, **required_periods** (every listed period needs at least one selected source), evidence budget, optional `required_source_ids`, minimum relevance.
- `build_context(records, policy) -> ContextResult`: `selected`, `excluded` (operator diagnostics), `status`, `missing_required`, `missing_periods`, `conflicts`, evidence token counts.
- `render_context(...)`: sections for application instructions, current task, structured execution state, JSON-serialized external evidence, and **privacy-reduced** outcome information. Rejected source IDs and missing required-source IDs are not exposed to the model. Enforces caller-supplied rendered input budget.
- `AgentState` / `Finding`: confirmed findings, hypotheses and unresolved items are separate typed fields.
- `ToolResultStore`: educational in-memory tool-result externalization by ID.

## Outcomes

- `ready`: all explicitly required source IDs and **all required periods** covered, no flagged conflicts.
- `insufficient_context`: at least one required source or period not represented in selected evidence (including budget exclusion).
- `review_required`: simple duplicate-version or same-claim-key disagreement detected, with all required evidence present.

**Exclusion reasons** (restricted/operator-only details): `unauthorized_scope`, `wrong_period`, `superseded`, `unverified`, `invalid_metadata`, `below_relevance_threshold`, `duplicate_older_version`, `duplicate_identical`, `conflicting_duplicate`, `over_budget`.

## Boundaries

Authorization must happen in the retrieval/access layer **before scoring**; the builder's tenant check is defense in depth only. `verified` is trusted upstream metadata, not proof of factual truth. Conflict detection is a literal-text heuristic, not semantic reconciliation. Neither JSON quotation nor labels stop prompt injection by themselves. The model must not be the action policy authority. Token costs in `Evidence` are supplied estimates; `render_context` requires a caller-supplied counter, and the example uses `len` as a **character-count demonstration, not a real model tokenizer**. In production, account for provider overhead and output reserve. ToolResultStore is not secure/durable. Restrict operator logs: even exclusion IDs may be sensitive.

## Publishing / public download

The ZIP supplied alongside this conversation is a valid chat download, **not a public Medium-hostable URL**. Before adding a public download link in Medium, publish the ZIP to a GitHub Release or another approved file host and use its actual verified URL. The article does not invent a public link.
