"""Deterministic orchestration contracts; no LLM integration is claimed."""
from dataclasses import dataclass
from enum import Enum

class Status(str, Enum):
    PENDING='pending'
    RUNNING='running'
    COMPLETED='completed'
    INSUFFICIENT_EVIDENCE='insufficient_evidence'
    FAILED='failed'
    BLOCKED='blocked'
    OUTCOME_UNKNOWN='outcome_unknown'
    CONFLICT='conflict'

@dataclass(frozen=True)
class Delegation:
    contract_version: str
    task_id: str
    parent_task_id: str
    correlation_id: str
    worker: str
    objective: str
    allowed_tools: tuple[str,...]
    evidence_ids: tuple[str,...]
    max_steps: int = 3
    deadline_seconds: float = 5.0
    attempt_budget: int = 1
    idempotency_key: str = ''
    side_effects_allowed: bool = False

@dataclass(frozen=True)
class Finding:
    factor: str
    value: float
    evidence_ids: tuple[str,...]
    source_version: str

@dataclass(frozen=True)
class Result:
    task_id: str
    status: Status
    findings: tuple[Finding,...] = ()
    reason: str = ''

class InvalidContract(ValueError): pass
class AccessDenied(PermissionError): pass
class OutcomeUnknown(RuntimeError): pass
