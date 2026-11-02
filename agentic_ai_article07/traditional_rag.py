"""Predefined multi-source retrieval baseline, deliberately limited to two topics."""
from retrieval import DOCUMENTS, Document, retrieve

def collect_traditional(tenant: str, *, authorized_tenants: frozenset[str], documents: tuple[Document, ...] = DOCUMENTS) -> tuple[Document, ...]:
    results = []
    for topic in ('revenue', 'churn'):
        results.extend(retrieve(tenant, topic, authorized_tenants=authorized_tenants, documents=documents))
    return tuple(results)
