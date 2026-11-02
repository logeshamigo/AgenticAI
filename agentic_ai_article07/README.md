# Article 07 — Agentic RAG vs Traditional RAG (v3.0)

**Agentic AI Engineering Series — Article 07 of 25**, Logesh Kumaraguru.

## Run

Requires Python 3.10+. No external packages, API keys, internet, or model provider.

```bash
python demo.py
python -m unittest discover -s tests -v
```

## What it shows

- `traditional_rag.py`: a fixed, intentionally limited retrieval plan for `revenue` and `churn`.
- `agentic_rag.py`: evidence-driven decisions: `revenue` first; `churn` only if a decline is found; `pricing` when the churn figure is not enough to account for the decline. A deterministic requirement check verifies both FY2025-Q2 and FY2026-Q2 revenue evidence.
- `retrieval.py`: synthetic tenant-isolated documents with `source` and `trust='untrusted_external'` provenance envelope fields.
- `demo.py`: same question and corpus for two retrieval strategies, plus budget-exhaustion example.
- `tests/test_retrieval.py`: 11 standard-library tests, including fiscal-period completeness, unavailable data on the exact budget boundary, invalid `all_accounts`, cross-tenant access, and budget exhaustion.

## Sample output

```text
Question: Why did total revenue fall from FY2025-Q2 to FY2026-Q2?
Traditional searched: revenue -> churn
Traditional sources: ['revenue-2025', 'revenue-2026', 'churn-2026']
Traditional coverage complete: False
Agentic searched: revenue -> churn -> pricing
Agentic sources: ['revenue-2025', 'revenue-2026', 'churn-2026', 'pricing-2026']
Agentic status: coverage_complete
Agentic calls: 3
Interpretation: synthetic attribution figures, not independent proof of causation.
Agentic max_calls=2 status: budget_exhausted
```

## IMPORTANT limitations

This is an **educational, evidence-adaptive retrieval simulation**, not LLM-powered RAG. The planner reads structured evidence, but is deterministic. An actual LLM planner could propose the next action via schema-validated output, with *the same runtime checks* retained.

This is **not** a production retrieval system: no embeddings, similarity scoring, reranker, live auth, token/time limit, real revocation, or generated answer. In production, run authenticated document/chunk-level ACL filters **before** candidate scoring, not after. `coverage_complete` means the scenario's required documents and period pairs were retrieved; it does **not** certify the correctness of a causal account. The dollar amounts are made up, and the accounting attribution does not prove causation. The fixed baseline is intentionally limited; capable predefined pipelines could retrieve pricing too.

## Reference

Article's LangGraph documentation link: https://docs.langchain.com/oss/python/langgraph/agentic-rag
