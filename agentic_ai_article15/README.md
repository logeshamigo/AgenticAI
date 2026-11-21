# Article 15 companion demo

Run from this directory using Python 3.10 or later.

```bash
python demo.py
python -m unittest discover -v
```

The first request returns the synthetic aggregate. The second request arrives after revocation and returns a denial. The audit entry records the subject, authenticated actor, workflow, and decision.

The fixtures prepopulate a trusted grant registry and treat caller identity and time as trusted inputs. A real service obtains identity from a verified authentication layer and time from its own trusted clock. This demonstration uses synchronous in-memory state and a fixed aggregate. It omits token issuance and validation, network transport, persistent audit storage, and synchronization with a live data store. The grant ID is a fixture lookup key. Detailed denial reasons are local diagnostics.
