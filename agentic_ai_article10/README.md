# Article 10 — Computer-Use Agents Demo (companion v2)

**Educational local-only demonstration** accompanying Article 10 of the Agentic AI Engineering series. The fictional browser app is run on `127.0.0.1` with an ephemeral port. It does not use any LLM/API key, production accounts, or external services.

## Installation (Python 3.10+)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Run

```bash
python run_demo.py                      # no approval: no writes
python run_demo.py --approve            # explicit approval: one write, verified
python run_demo.py --approve --headed   # observe a real browser
python -m unittest discover -s tests -v
```

The suite has **19 tests** (one real-Chromium test is skipped automatically if Chromium is not installed).

Expected output:

```text
$ python run_demo.py
Controller result: approval_required
Persisted ticket status: Open
Number of writes: 0

$ python run_demo.py --approve
Controller result: verified
Persisted ticket status: Resolved
Number of writes: 1
```

Each invocation starts a fresh fictional server state (`Open`). Checkpoint events append in `run_state.json`. No sensitive page content is persisted.

## Scope and safety

- The controller has an explicit allowlist of ticket `T-104` and three statuses.
- State-changing submission is blocked without `--approve`.
- UI actions are made using Playwright semantic locators. A separate read-only local status endpoint verifies the actual saved state.
- On uncertain submission results (including Playwright's own `TimeoutError`, which the adapter maps to `OutcomeUnknown`), the controller **never** blindly repeats a potentially consequential click; it verifies persisted state instead.
- `max_actions=0` blocks all state changes; any positive value still allows exactly one submission in this demo (it is a gate, not a multi-step budget).
- A locally scoped browser adapter rejects non-127.0.0.1 hosts; the demo's browser context aborts requests to other origins. This is a **code-level boundary, not a hardened OS sandbox or firewall**.
- Local test page contains intentionally malicious page text as a prompt-injection fixture. The controller does not interpret that text as an instruction.
- The decision logic is **deterministic**, not model-driven. It illustrates the interfaces and safeguards a real model-driven controller would require; it is **not** a general-purpose autonomous computer-use agent.
- For production deployment, additionally use isolated browser/container/VM environments, network egress controls, identity and credential boundaries, CSRF defenses, authenticated app sessions, redacted logs, audited approvals, and robust recovery.

## Files

- `agent.py`: bounded execution policy, approvals, verification, checkpoint events.
- `browser_adapter.py`: Playwright UI adapter.
- `local_app.py`: fictional local web application.
- `run_demo.py`: runnable browser integration.
- `tests/`: deterministic failure and policy tests.

References: https://playwright.dev/python/docs/locators ; https://developers.openai.com/api/docs/guides/tools-computer-use ; https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool
