"""Deterministic, sequential example workers; these are NOT LLM agents."""
from contracts import Delegation, Finding, Result, Status, AccessDenied
from evidence import EvidenceStore
from policy import authorize_tool

def execute_worker(d: Delegation, store: EvidenceStore, *, caller_tools=None, runtime_tools=None, fail=False):
    if fail:
        return Result(d.task_id, Status.FAILED, reason='injected worker failure')
    if not d.evidence_ids:
        return Result(d.task_id, Status.INSUFFICIENT_EVIDENCE, reason='no evidence')
    caller_tools = set(caller_tools if caller_tools is not None else ())
    runtime_tools = set(runtime_tools if runtime_tools is not None else ())
    try:
        records = []
        for identifier in d.evidence_ids:
            authorize_tool(d, 'read_report' if d.worker != 'verifier' else 'verify_evidence', caller_tools, runtime_tools)
            records.append(store.read(identifier, d.worker))
        # Arithmetic is a separate protected operation for the analyst.
        if d.worker == 'analyst':
            authorize_tool(d, 'calculate', caller_tools, runtime_tools)
    except (KeyError, PermissionError, ValueError) as exc:
        return Result(d.task_id, Status.BLOCKED if isinstance(exc, AccessDenied) else Status.FAILED, reason=str(exc))
    grouped = {}
    for r in records:
        grouped.setdefault((r.factor, r.version), []).append(r)
    # Deliberately conservative rule: opposing signed values within a factor/version
    # require reconciliation; do not silently net them to a successful conclusion.
    for group in grouped.values():
        if any(r.amount > 0 for r in group) and any(r.amount < 0 for r in group):
            return Result(d.task_id, Status.CONFLICT, reason='opposing signed values require reconciliation')
    findings = tuple(Finding(k[0], sum(r.amount for r in group), tuple(r.identifier for r in group), k[1])
                     for k, group in sorted(grouped.items()))
    return Result(d.task_id, Status.COMPLETED, findings)
