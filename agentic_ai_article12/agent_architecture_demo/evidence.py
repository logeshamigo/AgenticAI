from dataclasses import dataclass
from contracts import Finding

@dataclass(frozen=True)
class Evidence:
    identifier: str
    factor: str
    amount: float
    source: str
    version: str = 'v1'
    trusted: bool = True
    allowed_roles: tuple[str,...] = ('analyst','research','verifier')

class EvidenceStore:
    def __init__(self, records):
        if len({r.identifier for r in records}) != len(records):
            raise ValueError('duplicate evidence id')
        self._records={r.identifier:r for r in records}
    def read(self, identifier, role):
        e=self._records[identifier]
        if role not in e.allowed_roles: raise PermissionError('evidence role denied')
        if not e.trusted: raise ValueError('untrusted evidence')
        return e
    def verify(self, finding: Finding, role='verifier'):
        if not finding.evidence_ids:return False
        try:
            records=[self.read(i,role) for i in finding.evidence_ids]
        except (KeyError,PermissionError,ValueError):return False
        return all(r.factor==finding.factor and r.version==finding.source_version for r in records) and abs(sum(r.amount for r in records)-finding.value)<1e-9

FIXTURES = {
    'churn': [Evidence('E-101','churn',60,'churn-report-v1'),Evidence('E-102','pricing',10,'pricing-report-v1')],
    'pricing': [Evidence('E-201','churn',10,'churn-report-v1'),Evidence('E-202','pricing',70,'pricing-report-v1')],
    'mixed': [Evidence('E-301','churn',40,'churn-report-v1'),Evidence('E-302','pricing',35,'pricing-report-v1')],
    'incomplete': [Evidence('E-401','churn',30,'churn-report-v1')],
    'conflict': [Evidence('E-501','churn',50,'churn-report-v1'),Evidence('E-502','churn',-70,'churn-report-v1')],
}
