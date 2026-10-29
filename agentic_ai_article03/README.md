# Article 03 — Three agent orchestration patterns
Python 3.11+; install: `python -m pip install -r requirements.txt`.
Set `OPENAI_API_KEY` for the two LLM-powered examples.
- `python react_agent.py` — model-controlled iterative function calling.
- `python plan_execute.py` — structured LLM plan, allowlisted deterministic execution.
- `python graph_workflow.py` — graph-defined deterministic branching without LLM (shows orchestration, not model autonomy).
- `python -m unittest -v test_business.py` — no API key necessary.
The fixture data is fabricated; the scripts do not connect to carrier services.
The plan example is intentionally a single-pass planner; production replanning requires an explicit validator/replanner loop and max iterations.
`max_turns` counts model turns, not cost or wall-clock seconds.
Always pin and test package versions before publication/production.
