from contracts import Delegation,InvalidContract,AccessDenied
WORKER_TOOLS={'research': {'read_report'},'analyst': {'read_report','calculate'},'verifier': {'verify_evidence'}}

def enforce(d:Delegation, caller_tools: set[str], runtime_tools: set[str]):
    if d.contract_version!='1.0' or not d.task_id or not d.correlation_id or not d.parent_task_id: raise InvalidContract('invalid contract identity/version')
    if d.worker not in WORKER_TOOLS or d.max_steps<1 or d.attempt_budget<1 or d.deadline_seconds<=0:raise InvalidContract('invalid limits/worker')
    if len(set(d.allowed_tools))!=len(d.allowed_tools):raise InvalidContract('duplicate tool')
    permitted=caller_tools & WORKER_TOOLS[d.worker] & runtime_tools
    if not set(d.allowed_tools)<=permitted: raise AccessDenied('scope escalation blocked')
    if d.side_effects_allowed:raise AccessDenied('demo is read-only')
    return True


def authorize_tool(d: Delegation, tool: str, caller_tools: set[str], runtime_tools: set[str]):
    """Enforce permissions at every simulated tool operation, not just admission."""
    permitted = caller_tools & WORKER_TOOLS[d.worker] & runtime_tools & set(d.allowed_tools)
    if tool not in permitted:
        raise AccessDenied(f'tool denied at execution: {tool}')
