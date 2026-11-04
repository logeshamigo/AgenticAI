"""Framework-neutral memory engineering demo. Python 3.10+, stdlib only.

Illustrates explicit verified writes, namespace isolation, TTL, supersession,
retrieval, revocation and independently persisted execution checkpoints.
Not an LLM or embedding implementation.

Known demo limits: a new semantic record supersedes the active one with the same
key purely by recency (no authority ranking or effective-date ranges); retrieval
does not detect conflicts beyond supersession; only 'semantic' and 'episodic'
kinds are supported (no procedural memory).
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import re
import sqlite3
from typing import Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def normalize_expiry(value: str) -> str:
    """Return a UTC ISO-8601 string with fixed precision.

    Requires an explicit timezone (offset or trailing 'Z'). Normalising to UTC
    keeps the SQL string comparison in recall() chronologically correct.
    """
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("expires_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("expires_at must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


@dataclass(frozen=True)
class Candidate:
    tenant: str
    subject: str
    kind: str  # semantic or episodic
    key: str
    content: str
    source_id: str
    verified: bool
    expires_at: Optional[str] = None


class MemoryStore:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant TEXT NOT NULL, subject TEXT NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('semantic','episodic')),
            key TEXT NOT NULL, content TEXT NOT NULL,
            source_id TEXT NOT NULL, recorded_at TEXT NOT NULL,
            expires_at TEXT, status TEXT NOT NULL DEFAULT 'active'
                CHECK(status IN ('active','superseded','revoked'))
        );
        CREATE INDEX IF NOT EXISTS idx_memory_scope
            ON memory(tenant,subject,status,kind);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_active_semantic_key
            ON memory(tenant,subject,key)
            WHERE kind='semantic' AND status='active';
        CREATE TABLE IF NOT EXISTS checkpoints (
            tenant TEXT NOT NULL, run_id TEXT NOT NULL,
            state_json TEXT NOT NULL, saved_at TEXT NOT NULL,
            PRIMARY KEY(tenant, run_id)
        );
        """)

    def write(self, c: Candidate) -> int:
        if not all(isinstance(v, str) and v.strip() for v in
                   (c.tenant, c.subject, c.source_id, c.key, c.content)):
            raise ValueError("Scope, provenance, key and content required")
        if c.kind not in ("semantic", "episodic"):
            raise ValueError("Unsupported memory kind")
        if c.verified is not True:  # strict: a truthy string must not pass
            raise PermissionError("Unverified candidates cannot be stored")
        expires = None
        if c.expires_at:
            expires = normalize_expiry(c.expires_at)
            if expires <= utc_now():
                raise ValueError("Memory has already expired")
        with self.db:
            if c.kind == "semantic":
                self.db.execute("""UPDATE memory SET status='superseded'
                    WHERE tenant=? AND subject=? AND kind='semantic' AND key=?
                      AND status='active'""", (c.tenant, c.subject, c.key))
            cursor = self.db.execute("""INSERT INTO memory
                (tenant,subject,kind,key,content,source_id,recorded_at,expires_at)
                VALUES (?,?,?,?,?,?,?,?)""", (c.tenant, c.subject, c.kind,
                c.key, c.content, c.source_id, utc_now(), expires))
        return int(cursor.lastrowid)

    def recall(self, tenant: str, subject: str, query: str = "", limit: int = 5):
        if not tenant or not subject:
            raise ValueError("Explicit tenant and subject required")
        if not 1 <= limit <= 50:
            raise ValueError("Invalid limit")
        # Scope filter is applied in SQL before relevance matching, not afterward.
        rows = self.db.execute("""SELECT * FROM memory
            WHERE tenant=? AND subject=? AND status='active'
              AND (expires_at IS NULL OR expires_at > ?)
            ORDER BY id DESC""", (tenant, subject, utc_now())).fetchall()
        terms = set(re.findall(r"[a-z0-9]+", query.lower()))
        def score(row):
            haystack = set(re.findall(r"[a-z0-9]+", (row['key']+' '+row['content']).lower()))
            return len(terms & haystack)
        ranked = sorted(rows, key=lambda row: (score(row), row['id']), reverse=True)
        if terms:
            ranked = [row for row in ranked if score(row) > 0]
        return [dict(row) for row in ranked[:limit]]

    def revoke(self, tenant: str, subject: str, memory_id: int) -> bool:
        with self.db:
            cursor = self.db.execute("""UPDATE memory SET status='revoked'
                WHERE id=? AND tenant=? AND subject=? AND status='active'""",
                (memory_id, tenant, subject))
        return cursor.rowcount == 1

    def save_checkpoint(self, tenant: str, run_id: str, state: dict) -> None:
        if not tenant or not run_id:
            raise ValueError("Checkpoint scope required")
        with self.db:
            self.db.execute("""INSERT INTO checkpoints VALUES (?,?,?,?)
                ON CONFLICT(tenant,run_id) DO UPDATE SET
                state_json=excluded.state_json,saved_at=excluded.saved_at""",
                (tenant, run_id, json.dumps(state, sort_keys=True), utc_now()))

    def load_checkpoint(self, tenant: str, run_id: str) -> Optional[dict]:
        row = self.db.execute("""SELECT state_json FROM checkpoints
            WHERE tenant=? AND run_id=?""", (tenant, run_id)).fetchone()
        return json.loads(row['state_json']) if row else None

    def close(self):
        self.db.close()
