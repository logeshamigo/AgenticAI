"""Read-only supervisor: validates output, enforces limits and preserves uncertainty."""
from contracts import Delegation,Result,Status,Finding,AccessDenied,InvalidContract
from policy import enforce
from workers import execute_worker

class Supervisor:
    def __init__(self,store,caller_tools=None,runtime_tools=None):
        self.store=store
        self.caller_tools=set(caller_tools or {'read_report','calculate','verify_evidence'})
        self.runtime_tools=set(runtime_tools or {'read_report','calculate','verify_evidence'})
        self.seen=set()
        self.trace=[]
    def run(self, d:Delegation, *, simulated_timeout=False, fail=False, override_result=None):
        if d.task_id in self.seen:return Result(d.task_id,Status.BLOCKED,reason='duplicate task id')
        self.seen.add(d.task_id)
        self.trace.append(('received',d.task_id))
        try:enforce(d,self.caller_tools,self.runtime_tools)
        except (AccessDenied,InvalidContract) as ex:return Result(d.task_id,Status.BLOCKED,reason=str(ex))
        if simulated_timeout:
            # A timeout does not prove a remote side effect was absent.
            return Result(d.task_id,Status.OUTCOME_UNKNOWN,reason='timeout; reconciliation required')
        if override_result is not None:result=override_result
        else:result=execute_worker(d,self.store,caller_tools=self.caller_tools,runtime_tools=self.runtime_tools,fail=fail)
        if result.task_id!=d.task_id:return Result(d.task_id,Status.FAILED,reason='task mismatch')
        if result.status!=Status.COMPLETED:return result
        if not result.findings:return Result(d.task_id,Status.INSUFFICIENT_EVIDENCE,reason='empty findings')
        permitted_ids=set(d.evidence_ids)
        if any(not set(f.evidence_ids)<=permitted_ids or len(f.evidence_ids)!=len(set(f.evidence_ids)) for f in result.findings):
            return Result(d.task_id,Status.FAILED,reason='result cites evidence outside delegation or duplicates evidence')
        if not all(self.store.verify(f) for f in result.findings):return Result(d.task_id,Status.FAILED,reason='evidence validation failed')
        self.trace.append(('verified',d.task_id))
        return result

    def aggregate(self, results):
        # Caller controls ordering; stable sorted output for reproducibility.
        ordered=sorted(results,key=lambda r:r.task_id)
        if any(r.status==Status.OUTCOME_UNKNOWN for r in ordered):return {'status':'outcome_unknown','findings':[]}
        if any(r.status==Status.CONFLICT for r in ordered):return {'status':'conflict','findings':[]}
        if any(r.status in (Status.FAILED,Status.BLOCKED) for r in ordered):return {'status':'failed','findings':[]}
        if any(r.status==Status.INSUFFICIENT_EVIDENCE for r in ordered):return {'status':'insufficient_evidence','findings':[]}
        seen={}
        for r in ordered:
            for f in r.findings:
                key=(f.factor,f.source_version)
                if key in seen and seen[key].value != f.value:return {'status':'conflict','findings':[]}
                seen[key]=f
        findings=sorted(seen.values(),key=lambda f:(f.factor,f.source_version))
        return {'status':'completed','findings':[{'factor':f.factor,'value':f.value,'sources':list(f.evidence_ids)} for f in findings]}
