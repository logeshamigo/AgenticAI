import tempfile
from pathlib import Path
from hitl import ApprovalController

with tempfile.TemporaryDirectory() as folder:
    db_file = Path(folder) / "demo.sqlite3"
    c = ApprovalController(db_file)
    c.seed_ticket("T-104", tenant="acme", status="Open")
    print("Proposal:", c.propose("REQ-104", "acme", "T-104", "Resolved", "analyst-1", now=100))
    print("Execute before review:", c.execute("REQ-104", now=101))
    c.close()

    # Resume after process/controller restart; state lives in the database.
    c = ApprovalController(db_file)
    print("Review:", c.review("REQ-104", "reviewer-1", "approve", now=102))
    print("Execute after review:", c.execute("REQ-104", now=103))
    print("Final ticket:", c.ticket("T-104"))
    print("Writes:", c.writes())
    print("Audit:", c.audit_events("REQ-104"))
    c.close()
