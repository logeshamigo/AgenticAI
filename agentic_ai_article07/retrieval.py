"""Synthetic evidence and trusted retrieval gate. Not a production search index."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Document:
    id: str
    tenant: str
    topic: str
    period: str
    text: str
    amount_m: float | None = None
    source: str = 'synthetic-fixture'
    trust: str = 'untrusted_external'

DOCUMENTS = (
    Document('revenue-2025', 'acme', 'revenue', 'FY2025-Q2', 'Total revenue: $10.0M', 10.0),
    Document('revenue-2026', 'acme', 'revenue', 'FY2026-Q2', 'Total revenue: $8.4M', 8.4),
    Document('churn-2026', 'acme', 'churn', 'FY2026-Q2', 'Estimated revenue loss attributable to churn: $0.4M', 0.4),
    Document('pricing-2026', 'acme', 'pricing', 'FY2026-Q2', 'Estimated revenue loss attributable to pricing changes: $1.2M', 1.2),
    Document('other-private', 'other', 'revenue', 'FY2026-Q2', 'Other tenant revenue: confidential', 999.0),
)
ALLOWED_TOPICS = frozenset({'revenue', 'churn', 'pricing'})


def retrieve(tenant: str, topic: str, *, authorized_tenants: frozenset[str], documents=DOCUMENTS) -> tuple[Document, ...]:
    """Trusted gate: tenant authorization and topic allowlist precede candidate selection.

    Real systems must enforce authenticated user/role and chunk-level ACLs in
    their search backend BEFORE similarity scoring, not by post-filtering hits.
    """
    if tenant not in authorized_tenants:
        raise PermissionError('Cross-tenant retrieval denied')
    if topic not in ALLOWED_TOPICS:
        raise ValueError('Unsupported retrieval topic')
    return tuple(d for d in documents if d.tenant == tenant and d.topic == topic)
