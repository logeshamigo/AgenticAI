"""A fixed read-only baseline with one decision controller."""
from evidence import EvidenceStore

def run_single(records):
    store=EvidenceStore(records)
    findings={}
    for record in records:
        e=store.read(record.identifier,'analyst')
        findings[e.factor]=findings.get(e.factor,0)+e.amount
    return {'status':'completed' if {'churn','pricing'}<=findings.keys() else 'insufficient_evidence','findings':findings,'operations':len(records)}
