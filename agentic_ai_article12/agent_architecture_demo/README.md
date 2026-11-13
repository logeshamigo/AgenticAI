# Article 12 — Single-Agent vs Multi-Agent (deterministic companion)

This Python 3.10+ demo implements three orchestration shapes with the **same fixed evidence fixtures**: one controller, explicit predetermined extract/analyze/verify stages, and a sequential supervisor–worker. No API key or dependencies required.

## Run

```bash
cd agent_architecture_demo
python3 example.py
python3 evaluation.py
python3 -m unittest discover -s tests -v
```

## Guarantees and limits

- Read-only illustration of caller/worker/runtime tool intersection; it rejects side effects.
- Typed contracts, evidence IDs/provenance checks, result validation, duplicate IDs, deterministic aggregation, timeouts simulated as `outcome_unknown`.
- **No autonomous LLM workers or parallel execution**; **no real LLM inference**; no evidence of model accuracy, speed, tokens, or generalized multi-agent performance.
- Real remote tasks require durable state, cancellation acknowledgments, reconciliation, authenticated identities, and a trustworthy clock/scheduler. The demo's `deadline_seconds`, `max_steps`, and `attempt_budget` are contract validation fields; they do not enforce real-time execution limits. Its injected timeout is only a simulation, not worker cancellation.
- `verify` checks record membership and arithmetic for the fixture; it does not prove a business causal claim.
- `conflict` fixture contains +50 and -70 for churn. The supervisor now returns `conflict` even if pricing is present; this is a deliberately narrow signed-value check. The simpler baselines still net those values to -20. Production contradiction detection needs richer semantics.
- Do not expose this demo as a production service.

## Structure

- `contracts.py`: task/status schema
- `policy.py`: least privilege constraints
- `evidence.py`: provenance-aware, fixed dataset
- `workers.py`: deterministic worker
- `supervisor.py`: validation, aggregation and fault handling
- `single_agent.py`: one-controller baseline
- `workflow.py`: predefined stage pipeline
- `evaluation.py`: side-by-side fixture outputs
- `tests/`: offline unit tests

## Benchmark guidance

Real-model benchmark must fix model/version, dataset, tool access, prompt budgets and evaluation rubric. Measure repeated trials, task-level quality, latency, tokens, tool calls, cost, and failure modes. This example **does not** perform that benchmark.

## Tested release

40 passing unit tests on the bundled deterministic fixtures. Run from this directory with `python3 -m unittest discover -s tests -v`. Sequential workers do not demonstrate parallel speed-up. Actual external tool access, cancellation and side effects are not implemented.
