import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retrieval import DOCUMENTS, retrieve
from traditional_rag import collect_traditional
from agentic_rag import collect_agentic, requirement_state
AUTH = frozenset({'acme'})

class RetrievalTests(unittest.TestCase):
    def test_fixed_baseline_misses_pricing(self):
        docs = collect_traditional('acme', authorized_tenants=AUTH)
        self.assertFalse(requirement_state(docs)[0])
        self.assertNotIn('pricing-2026', [d.id for d in docs])

    def test_adaptive_uses_evidence_and_finds_pricing(self):
        r = collect_agentic('acme', authorized_tenants=AUTH)
        self.assertEqual(r.searched, ('revenue', 'churn', 'pricing'))
        self.assertEqual(r.status, 'coverage_complete')
        self.assertIn('pricing-2026', [d.id for d in r.documents])

    def test_missing_prior_year_baseline_is_insufficient(self):
        without = tuple(d for d in DOCUMENTS if d.id != 'revenue-2025')
        r = collect_agentic('acme', authorized_tenants=AUTH, documents=without)
        self.assertEqual(r.status, 'insufficient_evidence')
        self.assertFalse(r.coverage_complete)
        self.assertEqual(r.searched, ('revenue',))

    def test_empty_tenant_at_budget_boundary_is_insufficient(self):
        r = collect_agentic('empty', authorized_tenants=frozenset({'empty'}), max_calls=1)
        self.assertEqual(r.status, 'insufficient_evidence')
        self.assertEqual(r.calls, 1)

    def test_budget_exhaustion_before_required_search(self):
        r = collect_agentic('acme', authorized_tenants=AUTH, max_calls=2)
        self.assertEqual(r.status, 'budget_exhausted')
        self.assertEqual(r.searched, ('revenue', 'churn'))

    def test_zero_budget(self):
        self.assertEqual(collect_agentic('acme', authorized_tenants=AUTH, max_calls=0).status, 'budget_exhausted')

    def test_cross_tenant_denial(self):
        with self.assertRaises(PermissionError):
            retrieve('other', 'revenue', authorized_tenants=AUTH)

    def test_unapproved_all_accounts_denial(self):
        with self.assertRaises(ValueError):
            retrieve('acme', 'all_accounts', authorized_tenants=AUTH)

    def test_invalid_planner_denial(self):
        with self.assertRaises(ValueError):
            collect_agentic('acme', lambda remaining, evidence: 'all_accounts', authorized_tenants=AUTH)

    def test_trust_envelope(self):
        r = collect_agentic('acme', authorized_tenants=AUTH)
        self.assertTrue(all(d.source and d.trust == 'untrusted_external' for d in r.documents))

    def test_no_decline_stops_after_revenue(self):
        altered = tuple(d.__class__(d.id, d.tenant, d.topic, d.period, d.text, 11.0 if d.id == 'revenue-2026' else d.amount_m, d.source, d.trust) for d in DOCUMENTS)
        r = collect_agentic('acme', authorized_tenants=AUTH, documents=altered)
        self.assertEqual(r.searched, ('revenue',))
        self.assertEqual(r.status, 'coverage_complete')

if __name__ == '__main__':
    unittest.main()
