# Article 14 · Agent-to-Agent Interoperability

Companion to the Agentic AI Engineering Series by Logesh Kumaraguru.

Run with Python 3.10+ from the extracted directory. The project uses the Python standard library.

```bash
python demo.py
python -m unittest discover -v
```

The demo uses two SQLite databases and in-process calls to model separate owners. It loses the acknowledgement after the remote acceptance commits, reopens the coordinator database, and retries the same submission key. The specialist can then finish before the cancellation call and the coordinator retains that result without changing the finalized report.

The simulation uses canonical request strings, a single trusted specialist, simulated observation time, and application-defined task revisions. The pricing finding is treated as prevalidated. It omits network transport, A2A bindings, authentication, outbox delivery, automated retry scheduling, and source comparison. Production deployments should supply those components where required, use a real clock policy, and test their own provider's contract.
