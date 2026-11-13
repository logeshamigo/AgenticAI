"""Fixture-based architecture comparison; NOT an LLM performance benchmark."""
import json
from contracts import Delegation
from evidence import EvidenceStore,FIXTURES
from single_agent import run_single
from workflow import run_workflow
from supervisor import Supervisor

def compare(name):
    rows=FIXTURES[name]
    single=run_single(rows)
    staged=run_workflow(rows)
    sup=Supervisor(EvidenceStore(rows))
    tasks=[]
    for factor in ('churn','pricing'):
        ids=tuple(r.identifier for r in rows if r.factor==factor)
        tasks.append(Delegation('1.0',f'{name}-{factor}','q3','corr-q3','analyst',f'Analyze {factor}',('read_report','calculate'),ids))
    result=sup.aggregate([sup.run(d) for d in tasks])
    return {'dataset':name,'single':single,'workflow':staged,'supervisor':result,'note':'Sequential deterministic functions; no real model inference, parallelism, latency, tokens or accuracy claims.'}

if __name__=='__main__':
    print(json.dumps([compare(name) for name in FIXTURES],indent=2))
