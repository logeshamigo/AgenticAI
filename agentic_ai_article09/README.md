# Article 09 — Memory Engineering for AI Agents (companion v2)

Framework-neutral educational example. Python 3.10+, standard library only (SQLite). No API key.

## Run (from the extracted project folder)

```bash
python3 demo.py
python3 -m unittest -v test_memory_engine.py
```

The test suite contains **26 automated tests**.

Expected `demo.py` output:

```text
Recalled: [('semantic', 'report_period'), ('episodic', 'analysis-2026-10-10')]
Resume: {'approved': False, 'step': 'validate_revenue'}
```

## Files

- `memory_engine.py` — `MemoryStore` (verified writes, scoped recall, supersession, TTL, revocation, separate checkpoint table).
- `demo.py` — the Q3 revenue investigation scenario from the article.
- `test_memory_engine.py` — 26 tests, including expiry-timezone, strict-verification and database-uniqueness regressions.

## What it demonstrates

Tenant + subject scope applied in SQL before relevance matching; a `verified` write gate; semantic supersession; episodic entries; time-based expiry (timezone-aware, normalised to UTC); soft revocation; lexical recall; execution checkpoints stored separately from memories.

## Known limits (by design)

- Supersession is **by recency only**: a later semantic write with the same key replaces the active one regardless of source authority. Authority ranking, effective-date ranges and reconciliation with an authoritative configuration are left to the caller.
- Retrieval filters by scope, status and expiry. It does **not** detect conflicts beyond supersession.
- Only `semantic` and `episodic` kinds are supported. Procedural memory is intentionally out of scope.
- `verified` is a boolean supplied by a trusted caller; it is not a verification system. Real authorization is the caller's responsibility.
- Revocation is a soft delete, not physical erasure. No encryption, migrations, distributed concurrency, embeddings, vector search or LLM calls.
- `expires_at` must be an ISO-8601 timestamp with an explicit timezone (offset or `Z`).
- Memory content must be treated as untrusted data, never as system instruction.
