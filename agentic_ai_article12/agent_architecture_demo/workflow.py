"""Three explicit deterministic stages, centrally controlled (not autonomous agents)."""
from evidence import EvidenceStore

def extract(records):
    store = EvidenceStore(records)
    return [store.read(r.identifier, 'analyst') for r in records]

def analyze(extracted):
    totals = {}
    for record in extracted:
        totals[record.factor] = totals.get(record.factor, 0) + record.amount
    return totals

def verify(totals):
    return 'completed' if {'churn','pricing'} <= totals.keys() else 'insufficient_evidence'

def run_workflow(records):
    extracted = extract(records)
    findings = analyze(extracted)
    status = verify(findings)
    return {'status':status,'findings':findings,'operations':len(extracted),'stages':('extract','analyze','verify')}
