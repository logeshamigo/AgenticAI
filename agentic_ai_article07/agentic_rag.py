"""Evidence-driven, bounded retrieval simulation; no LLM is invoked."""
from dataclasses import dataclass
from collections.abc import Callable
from retrieval import Document, DOCUMENTS, retrieve

BASELINE = frozenset({('revenue', 'FY2025-Q2'), ('revenue', 'FY2026-Q2')})
MAX_CALLS = 3
Planner = Callable[[frozenset[str], tuple[Document, ...]], str]

@dataclass(frozen=True)
class RetrievalResult:
    documents: tuple[Document, ...]
    coverage_complete: bool
    calls: int
    status: str
    searched: tuple[str, ...]


def requirement_state(evidence: tuple[Document, ...]) -> tuple[bool, frozenset[str]]:
    """Deterministic evidence requirement check, NOT a proof of business causation."""
    keys = {(d.topic, d.period) for d in evidence}
    if not BASELINE.issubset(keys):
        return False, frozenset({'revenue'})
    by_key = {(d.topic, d.period): d for d in evidence}
    earlier = by_key['revenue', 'FY2025-Q2'].amount_m
    current = by_key['revenue', 'FY2026-Q2'].amount_m
    if earlier is None or current is None:
        return False, frozenset({'revenue'})
    decline = round(earlier - current, 6)
    if decline <= 0:
        return True, frozenset()  # No decline to investigate in this fixture
    churn = by_key.get(('churn', 'FY2026-Q2'))
    if churn is None or churn.amount_m is None:
        return False, frozenset({'churn'})
    if churn.amount_m + 1e-9 < decline:
        if ('pricing', 'FY2026-Q2') not in keys:
            return False, frozenset({'pricing'})
    return True, frozenset()


def evidence_aware_planner(remaining: frozenset[str], evidence: tuple[Document, ...]) -> str:
    """Reads prior evidence to choose next topic, rather than a fixed search order."""
    complete, needed = requirement_state(evidence)
    choices = needed & remaining
    if not complete and choices:
        return sorted(choices)[0]
    # Only used if a required topic was already searched but still missing.
    raise ValueError('No useful new retrieval decision')


def collect_agentic(tenant: str, choose_topic: Planner = evidence_aware_planner,
                    *, authorized_tenants: frozenset[str], max_calls: int = MAX_CALLS,
                    documents: tuple[Document, ...] = DOCUMENTS) -> RetrievalResult:
    if max_calls < 0:
        raise ValueError('max_calls must be nonnegative')
    evidence: dict[str, Document] = {}
    searched: list[str] = []
    while True:
        current = tuple(evidence.values())
        complete, needed = requirement_state(current)
        if complete:
            status = 'coverage_complete'
            break
        remaining = frozenset(needed - set(searched))
        # No useful NEW retrieval left: insufficient evidence, even on budget boundary.
        if not remaining:
            status = 'insufficient_evidence'
            break
        if len(searched) >= max_calls:
            status = 'budget_exhausted'
            break
        topic = choose_topic(remaining, current)
        if topic not in remaining:
            raise ValueError('Planner proposed unauthorized/repeated/unneeded topic')
        results = retrieve(tenant, topic, authorized_tenants=authorized_tenants, documents=documents)
        searched.append(topic)
        evidence.update({d.id: d for d in results})
    return RetrievalResult(tuple(evidence.values()), status == 'coverage_complete', len(searched), status, tuple(searched))
