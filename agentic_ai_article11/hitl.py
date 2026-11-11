"""Article 11: deterministic, approval-bound ticket execution; local SQLite only.

No LLM, API, browser, identity provider or remote side-effect.
The caller supplies an *already authenticated* reviewer identity. Never trust an
arbitrary client-provided reviewer ID in a production API.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path


class PolicyDenied(Exception):
    pass


class InvalidTransition(Exception):
    pass


def _fingerprint(tenant: str, ticket: str, target: str, expected_version: int) -> str:
    args = {"tenant": tenant, "ticket": ticket, "target": target, "expected_version": expected_version}
    return hashlib.sha256(json.dumps(args, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


ALLOWED_TARGETS = frozenset({"Resolved"})


class ApprovalController:
    def __init__(self, db_path: str | Path, reviewer_scopes: dict[str, frozenset[str]] | None = None):
        self.db = sqlite3.connect(str(db_path), timeout=15, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.reviewer_scopes = reviewer_scopes if reviewer_scopes is not None else {"reviewer-1": frozenset({"acme"})}  # Demo role + tenant scopes; NOT authentication
        self.db.executescript("""
            PRAGMA foreign_keys = ON;
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY, tenant TEXT NOT NULL,
                status TEXT NOT NULL, version INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS requests (
                request_id TEXT PRIMARY KEY, tenant TEXT NOT NULL,
                ticket_id TEXT NOT NULL, target TEXT NOT NULL,
                expected_version INTEGER NOT NULL, requester TEXT NOT NULL,
                created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
                status TEXT NOT NULL, approved_by TEXT,
                action_digest TEXT NOT NULL,
                FOREIGN KEY(ticket_id) REFERENCES tickets(ticket_id)
            );
            CREATE TABLE IF NOT EXISTS effects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL UNIQUE, ticket_id TEXT NOT NULL,
                resulting_status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL, event TEXT NOT NULL,
                actor TEXT NOT NULL, at_time INTEGER NOT NULL
            );
        """)

    def close(self):
        self.db.close()

    def seed_ticket(self, ticket_id: str, tenant: str, status: str = "Open", version: int = 1):
        self.db.execute(
            "INSERT INTO tickets(ticket_id,tenant,status,version) VALUES (?,?,?,?)",
            (ticket_id, tenant, status, version),
        )

    def ticket(self, ticket_id: str) -> dict:
        row = self.db.execute("SELECT * FROM tickets WHERE ticket_id=?", (ticket_id,)).fetchone()
        if not row:
            raise KeyError(ticket_id)
        return dict(row)

    def get_request(self, request_id: str) -> dict:
        row = self.db.execute("SELECT * FROM requests WHERE request_id=?", (request_id,)).fetchone()
        if not row:
            raise KeyError(request_id)
        return dict(row)

    def _audit(self, rid: str, event: str, actor: str, now: int):
        self.db.execute("INSERT INTO audit(request_id,event,actor,at_time) VALUES (?,?,?,?)", (rid,event,actor,now))

    def propose(self, rid: str, tenant: str, ticket_id: str, target: str,
                requester: str, now: int, ttl_seconds: int = 3600) -> str:
        if not rid or not tenant or not ticket_id or not requester or ttl_seconds <= 0:
            raise PolicyDenied("Invalid request identity or expiry")
        if target not in ALLOWED_TARGETS:  # Explicit demo policy: only resolve tickets
            raise PolicyDenied("Target status not allowed")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            t = self.db.execute("SELECT * FROM tickets WHERE ticket_id=?", (ticket_id,)).fetchone()
            if not t or t["tenant"] != tenant:
                raise PolicyDenied("Ticket not found within authorized tenant")
            if t["status"] == target:
                raise PolicyDenied("Ticket already has target status")
            expected_version = t["version"]
            digest = _fingerprint(tenant, ticket_id, target, expected_version)
            self.db.execute("""
                INSERT INTO requests(request_id,tenant,ticket_id,target,expected_version,
                    requester,created_at,expires_at,status,approved_by,action_digest)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (rid,tenant,ticket_id,target,expected_version,requester,now,
                  now+ttl_seconds,"pending",None,digest))
            self._audit(rid, "proposed", requester, now)
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        return "pending"

    def _expire_if_needed(self, row: sqlite3.Row, now: int) -> bool:
        if now >= row["expires_at"]:
            self.db.execute("UPDATE requests SET status='expired' WHERE request_id=?", (row["request_id"],))
            self._audit(row["request_id"], "expired", "system", now)
            return True
        return False

    def expire_requests(self, now: int) -> int:
        """Explicit periodic sweep: expire outstanding pending/approved requests.

        The demo has no background scheduler. Call from a trusted scheduler/worker
        to keep persisted records current when nobody reviews or executes them.
        Returns the number of newly expired requests; safe to call repeatedly.
        """
        self.db.execute("BEGIN IMMEDIATE")
        try:
            due = self.db.execute(
                "SELECT request_id FROM requests "
                "WHERE status IN ('pending','approved') AND expires_at <= ? "
                "ORDER BY request_id", (now,)
            ).fetchall()
            for row in due:
                rid = row["request_id"]
                self.db.execute("UPDATE requests SET status='expired' WHERE request_id=?", (rid,))
                self._audit(rid, "expired", "system", now)
            self.db.execute("COMMIT")
            return len(due)
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def review(self, rid: str, reviewer: str, decision: str, now: int) -> str:
        if decision not in {"approve", "reject"}:
            raise PolicyDenied("Decision must be approve or reject")
        if reviewer not in self.reviewer_scopes:
            raise PolicyDenied("Reviewer lacks permission")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            r = self.db.execute("SELECT * FROM requests WHERE request_id=?", (rid,)).fetchone()
            if not r:
                raise KeyError(rid)
            if r["status"] != "pending":
                raise InvalidTransition("Only pending requests can be reviewed")
            if r["tenant"] not in self.reviewer_scopes[reviewer]:
                raise PolicyDenied("Reviewer not authorized for request tenant")
            if reviewer == r["requester"]:
                raise PolicyDenied("Separation of duties: requester cannot approve")
            if self._expire_if_needed(r, now):
                self.db.execute("COMMIT")
                return "expired"
            new_status = "approved" if decision == "approve" else "rejected"
            self.db.execute("UPDATE requests SET status=?, approved_by=? WHERE request_id=?",
                            (new_status,reviewer if decision == "approve" else None,rid))
            self._audit(rid, new_status, reviewer, now)
            self.db.execute("COMMIT")
            return new_status
        except Exception:
            self.db.execute("ROLLBACK")
            raise

    def execute(self, rid: str, now: int, simulate_lost_response: bool = False) -> str:
        """Atomic local DB transaction; NOT a guarantee for an external API."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            r = self.db.execute("SELECT * FROM requests WHERE request_id=?", (rid,)).fetchone()
            if not r:
                raise KeyError(rid)
            if r["status"] == "executed":
                self.db.execute("COMMIT")
                return "already_executed"
            if r["status"] in {"pending", "approved"} and self._expire_if_needed(r, now):
                self.db.execute("COMMIT")
                return "expired"
            if r["status"] in {"pending", "rejected", "expired", "stale", "blocked"}:
                self.db.execute("COMMIT")
                return r["status"]
            if r["status"] != "approved":
                raise InvalidTransition("Unknown status")
            # Runtime policy is checked again after approval, at ACTION time.
            # Approval is not a bypass for policy changes or reviewer revocation.
            approver_scopes = self.reviewer_scopes.get(r["approved_by"])
            allowed = (
                r["target"] in ALLOWED_TARGETS
                and bool(r["approved_by"])
                and approver_scopes is not None
                and r["tenant"] in approver_scopes
                and r["approved_by"] != r["requester"]
            )
            if not allowed:
                self.db.execute("UPDATE requests SET status='blocked' WHERE request_id=?", (rid,))
                self._audit(rid, "blocked", "policy", now)
                self.db.execute("COMMIT")
                return "blocked"
            expected_digest = _fingerprint(r["tenant"],r["ticket_id"],r["target"],r["expected_version"])
            if expected_digest != r["action_digest"]:
                raise PolicyDenied("Approved action differs from stored proposal")
            t = self.db.execute("SELECT * FROM tickets WHERE ticket_id=?", (r["ticket_id"],)).fetchone()
            if not t or t["tenant"] != r["tenant"] or t["version"] != r["expected_version"]:
                self.db.execute("UPDATE requests SET status='stale' WHERE request_id=?", (rid,))
                self._audit(rid, "stale", "system", now)
                self.db.execute("COMMIT")
                return "stale"
            self.db.execute("UPDATE tickets SET status=?,version=version+1 WHERE ticket_id=?",
                            (r["target"],r["ticket_id"]))
            self.db.execute("INSERT INTO effects(request_id,ticket_id,resulting_status) VALUES (?,?,?)",
                            (rid,r["ticket_id"],r["target"]))
            self.db.execute("UPDATE requests SET status='executed' WHERE request_id=?", (rid,))
            self._audit(rid, "executed", "system", now)
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        if simulate_lost_response:
            raise TimeoutError("Simulated response loss AFTER local transaction committed")
        return "verified" if self.ticket(r["ticket_id"])["status"] == r["target"] else "not_verified"

    def writes(self) -> int:
        return self.db.execute("SELECT count(*) FROM effects").fetchone()[0]

    def audit_events(self, rid: str) -> list[str]:
        return [x[0] for x in self.db.execute("SELECT event FROM audit WHERE request_id=? ORDER BY id", (rid,))]
