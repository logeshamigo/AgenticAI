# Article 16 — Agent Evaluation Companion

A **model-driven experimental starter**, not a published benchmark result. All documents are synthetic. The experiment compares single-agent, structured-workflow, and supervisor/worker role schedules under a common model, corpus, retrieval tools, six research actions and one synthesis action. The supervisor/worker version changes role prompts and passes each role a sliced history of prior search/read actions, while every role receives the complete content of all documents read so far via shared document reads. It has no independent worker evidence isolation, separate processes, or distributed agents. **It must not be cited as a full multi-agent production implementation.**

## Run

```bash
cd agentic_ai_article16
python -m unittest -v test_benchmark.py
export OPENAI_API_KEY='your-key'
export EVAL_MODEL='gpt-4.1-mini'  # choose an accessible model supporting JSON output
python benchmark.py --trials 10 --model "$EVAL_MODEL" --max-tokens 6000 --output results
```

`summary.csv` gives per-trial measurements and `trials.jsonl` includes traces. Do not publish a win rate until real trials are executed. The 18 deterministic tests include malformed tool/model responses, grading invariants, HTTP parameter selection, and rerun consistency. Test files validate fixture and controller assumptions; they do NOT validate model correctness. Runs incur API costs.

## Live smoke test (2026-11-25)

A small live check with the code and prompts exactly as released: `--trials 2 --max-tokens 6000`, i.e. 2 seeds x 3 architectures = 6 runs per model. "Correct" is the strict grader result (D04 read, valid citations, churn `flat`, both drivers).

| Model | Correct | Avg tokens/run |
|---|---|---|
| `gpt-4.1` | 6/6 | ~3,900 |
| `gpt-4.1-mini` | 6/6 | ~3,800 |
| `gpt-5.4` | 6/6 | ~4,000 |
| `gpt-5.4-mini` | 6/6 | ~3,900 |
| `gpt-5.5` | 6/6 | ~4,800 |
| `gpt-5.6-sol` | 6/6 | ~4,300 |
| `gpt-6-luna` | 6/6 | ~4,500 |

Models that did not complete the protocol in the same test: `gpt-5.6-terra` 3/6, `gpt-6.1-terra` 0/6 and `gpt-6.2-sol` 0/6. The two 0/6 models issued another SEARCH at the final step instead of a final answer; no API errors were involved.

This is a smoke test that the harness runs end to end, not a benchmark: 6 runs per model is far too few to rank models or architectures. Results depend on model version and provider behavior at the time of the run.

## Experimental limitations

1. Equal *caps* are enforced for model calls (seven), tool calls (six), and token budget; actual token usage differs and must be reported.
2. Role prompts and sliced **action history** are the intended treatment. All roles receive the same full text of every document read so far. This is **not** independent worker specialization or a full multi-agent platform, and cannot isolate every confound.
3. SEARCH returns snippets containing facts; discovery is counted only on READ of D04; search behavior is deterministic within a seed.
4. The `gpt-4.1-mini` example uses temperature 0; reasoning-model requests omit temperature and use max_completion_tokens. Seeded ranking tie-breaks, order randomization and repeated runs reduce but do not eliminate variance.
5. No independent prompt optimization, leakage screening, model/provider outage normalization, confidence intervals, or holdout split is provided. Extend before publishing strong architecture claims.
6. Cost requires model/provider price schedule and actual input/output token splits; total token count here is a cost proxy only.
7. `valid_citations` is 0 for empty, absent, malformed or unread citations. `policy_compliant` checks that citations do not include unread evidence and the run has no provider failure; an explicit `unknown` abstention without citations can remain compliant. This field is **not** a comprehensive enterprise safety assessment.
8. The final grader requires an explicit `drivers` list containing exactly normalized `discounting` and `pricing mix`. This is a narrow synthetic-fact check, **not** natural-language negation or broad semantic entailment grading.
9. A run starts with fresh `summary.csv` and `trials.jsonl` files in its output folder; per-trial CSV snapshots are written so completed results survive interruptions. Use a distinct output folder for archival comparisons.
10. Model-specific API support needs live validation; see the smoke test above for the models tried so far (2 trials each). HTTP error bodies are recorded with truncation; avoid including secrets in error responses or sharing raw logs publicly.
11. A robust follow-up study should use a larger sealed corpus, independent gold annotations, separate worker contexts, parallel latency accounting, multi-model replication, and adversarial cases.


## Publication assets

Animated figures and the Medium article are maintained **separately** from this public runtime source bundle. The visualization generator was intentionally excluded because its previous version depended on container-specific paths and fonts. Refer to the published article for the figures.
