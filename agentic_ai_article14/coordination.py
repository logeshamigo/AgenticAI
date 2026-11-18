"""Local simulation with independent coordinator and specialist SQLite databases."""
from contextlib import closing, contextmanager
from dataclasses import dataclass
from hashlib import sha256
import sqlite3

TERMINAL = {"completed", "canceled"}


class ContractConflict(ValueError):
    """A repeated key or revision disagrees with its original payload."""


@dataclass(frozen=True)
class Snapshot:
    task_id: int
    revision: int
    status: str
    finding: str | None = None


@contextmanager
def transaction(path):
    with closing(sqlite3.connect(path)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN IMMEDIATE")
        yield db


class Specialist:
    def __init__(self, path):
        self.path = path
        with transaction(path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, submission_key TEXT UNIQUE NOT NULL,
                fingerprint TEXT NOT NULL, revision INTEGER NOT NULL,
                status TEXT NOT NULL, finding TEXT
            )""")

    def submit(self, key, request):
        fingerprint = sha256(request.encode()).hexdigest()
        with transaction(self.path) as db:
            db.execute("""INSERT INTO tasks (submission_key, fingerprint, revision, status)
                          VALUES (?, ?, 1, 'working')
                          ON CONFLICT(submission_key) DO NOTHING""", (key, fingerprint))
            row = db.execute("SELECT * FROM tasks WHERE submission_key = ?", (key,)).fetchone()
            if row["fingerprint"] != fingerprint:
                raise ContractConflict("submission key already binds to a different request")
            return self._snapshot(row)

    def get(self, task_id):
        with transaction(self.path) as db:
            return self._snapshot(self._get(db, task_id))

    def finish(self, task_id, finding):
        return self._transition(task_id, "completed", finding)

    def cancel(self, task_id):
        return self._transition(task_id, "canceled", None)

    def _transition(self, task_id, status, finding):
        with transaction(self.path) as db:
            db.execute("""UPDATE tasks SET revision = revision + 1, status = ?, finding = ?
                          WHERE id = ? AND status = 'working'""", (status, finding, task_id))
            return self._snapshot(self._get(db, task_id))

    @staticmethod
    def _get(db, task_id):
        row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        return row

    @staticmethod
    def _snapshot(row):
        return Snapshot(row["id"], row["revision"], row["status"], row["finding"])


class Coordinator:
    def __init__(self, path):
        self.path = path
        with transaction(path) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS delegations (
                submission_key TEXT PRIMARY KEY, request TEXT NOT NULL,
                deadline INTEGER NOT NULL, task_id INTEGER, revision INTEGER NOT NULL DEFAULT 0,
                remote_status TEXT, remote_finding TEXT, adopted_finding TEXT,
                finalized INTEGER NOT NULL DEFAULT 0, cancel_requested INTEGER NOT NULL DEFAULT 0
            )""")

    def prepare(self, key, request, deadline):
        with transaction(self.path) as db:
            db.execute("""INSERT INTO delegations (submission_key, request, deadline)
                          VALUES (?, ?, ?) ON CONFLICT(submission_key) DO NOTHING""",
                       (key, request, deadline))
            row = self._get(db, key)
            if (row["request"], row["deadline"]) != (request, deadline):
                raise ContractConflict("local delegation already binds to a different contract")

    def dispatch(self, specialist, key, observed_at, *, lose_ack=False):
        row = self.state(key)
        if row["task_id"] is not None:
            return self.reconcile(specialist, key, observed_at)
        snapshot = specialist.submit(key, row["request"])
        if lose_ack:
            raise TimeoutError("specialist accepted before acknowledgement was lost")
        return self.observe(key, snapshot, observed_at, bind_submission=True)

    def reconcile(self, specialist, key, observed_at):
        snapshot = specialist.get(self.state(key)["task_id"])
        return self.observe(key, snapshot, observed_at)

    def observe(self, key, snapshot, observed_at, *, bind_submission=False):
        """Apply a correlated snapshot from the trusted in-process specialist."""
        with transaction(self.path) as db:
            row = self._get(db, key)
            if row["task_id"] != snapshot.task_id and not (
                row["task_id"] is None and bind_submission
            ):
                raise ContractConflict("snapshot belongs to a different or unbound task")
            if snapshot.revision < row["revision"]:
                return "stale"
            if snapshot.revision == row["revision"]:
                if (snapshot.status, snapshot.finding) != (row["remote_status"], row["remote_finding"]):
                    raise ContractConflict("same revision has a different payload")
                return "duplicate"
            if row["remote_status"] in TERMINAL:
                raise ContractConflict("terminal task received a newer revision")

            adopted = row["adopted_finding"]
            if snapshot.status == "completed" and observed_at < row["deadline"] and not row["finalized"]:
                adopted = snapshot.finding
            db.execute("""UPDATE delegations SET task_id = ?, revision = ?, remote_status = ?,
                          remote_finding = ?, adopted_finding = ? WHERE submission_key = ?""",
                       (snapshot.task_id, snapshot.revision, snapshot.status,
                        snapshot.finding, adopted, key))
            return "applied"

    def finalize(self, key):
        with transaction(self.path) as db:
            self._get(db, key)
            db.execute("UPDATE delegations SET finalized = 1 WHERE submission_key = ?", (key,))

    def request_cancel(self, specialist, key, observed_at):
        with transaction(self.path) as db:
            task_id = self._get(db, key)["task_id"]
            if task_id is None:
                raise ValueError("recover the task ID before requesting cancellation")
            db.execute("UPDATE delegations SET cancel_requested = 1 WHERE submission_key = ?", (key,))
        return self.observe(key, specialist.cancel(task_id), observed_at)

    def state(self, key):
        with transaction(self.path) as db:
            return dict(self._get(db, key))

    @staticmethod
    def _get(db, key):
        row = db.execute("SELECT * FROM delegations WHERE submission_key = ?", (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        return row
