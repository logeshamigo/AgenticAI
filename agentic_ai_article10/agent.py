"""Bounded, deterministic computer-use controller. No LLM or production credentials."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import json

ALLOWED_TICKET = 'T-104'
ALLOWED_STATUSES = frozenset({'Open', 'In Progress', 'Resolved'})

class PolicyDenied(Exception): pass
class OutcomeUnknown(Exception): pass
class VerificationFailed(Exception): pass

class UIAdapter(Protocol):
    def observe(self, ticket_id: str) -> str: ...
    def submit(self, ticket_id: str, status: str) -> None: ...
    def verify(self, ticket_id: str) -> str: ...

@dataclass(frozen=True)
class Task:
    ticket_id: str
    target_status: str
    approved: bool = False

class Checkpoints:
    def __init__(self, filename: str | Path): self.filename = Path(filename)
    def record(self, **fields):
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        data = json.loads(self.filename.read_text()) if self.filename.exists() else {'events': []}
        # Never persist credentials, page bodies, or untrusted ticket descriptions.
        data['events'].append(fields)
        tmp = self.filename.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self.filename)

class Controller:
    def __init__(self, ui: UIAdapter, checkpoints: Checkpoints, max_actions: int = 1):
        # 0 disables all state changes; any positive value still permits exactly one submission in this demo.
        if max_actions < 0: raise ValueError('max_actions must be nonnegative')
        self.ui, self.checkpoints, self.max_actions = ui, checkpoints, max_actions

    def run(self, task: Task) -> str:
        # Enforced before observing, navigating, or making a state change.
        if task.ticket_id != ALLOWED_TICKET or task.target_status not in ALLOWED_STATUSES:
            raise PolicyDenied('Ticket or status is not allowlisted')
        before = self.ui.observe(task.ticket_id)
        self.checkpoints.record(stage='observed', ticket=task.ticket_id, status=before)
        if before == task.target_status:
            self.checkpoints.record(stage='verified', ticket=task.ticket_id, status=before)
            return 'already_verified'
        if not task.approved:
            self.checkpoints.record(stage='approval_required', ticket=task.ticket_id)
            return 'approval_required'
        if self.max_actions == 0:
            self.checkpoints.record(stage='stopped_budget', ticket=task.ticket_id)
            return 'stopped_budget'
        # Exactly one potentially consequential submission. Uncertain outcomes are verified,
        # never retried automatically.
        try:
            self.ui.submit(task.ticket_id, task.target_status)
            self.checkpoints.record(stage='action_delivered', ticket=task.ticket_id)
        except (TimeoutError, OutcomeUnknown):
            self.checkpoints.record(stage='uncertain_submission', ticket=task.ticket_id)
        try:
            after = self.ui.verify(task.ticket_id)
        except Exception as exc:
            self.checkpoints.record(stage='verification_unavailable', ticket=task.ticket_id)
            raise VerificationFailed('Authoritative verification unavailable; no retry permitted') from exc
        if after == task.target_status:
            self.checkpoints.record(stage='verified', ticket=task.ticket_id, status=after)
            return 'verified'
        self.checkpoints.record(stage='not_verified', ticket=task.ticket_id, status=after)
        raise VerificationFailed('Task outcome not verified; no automatic resubmission')
