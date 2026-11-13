import unittest
from dataclasses import replace
from contracts import Delegation,Finding,Result,Status
from evidence import Evidence, EvidenceStore, FIXTURES
from policy import enforce
from supervisor import Supervisor
from single_agent import run_single
from workflow import run_workflow
from evaluation import compare

class DemoTests(unittest.TestCase):
    def setUp(self):
        self.store=EvidenceStore(FIXTURES['mixed'])
        self.sup=Supervisor(self.store)
        self.d=Delegation('1.0','t1','root','corr','analyst','analyze',('read_report','calculate'),('E-301',))
    def test_success(self):self.assertEqual(self.sup.run(self.d).status,Status.COMPLETED)
    def test_verified_trace(self):self.assertIn(('verified','t1'),self.sup.run(self.d) if False else (self.sup.run(self.d),self.sup.trace)[1])
    def test_duplicate(self):self.sup.run(self.d);self.assertEqual(self.sup.run(self.d).status,Status.BLOCKED)
    def test_bad_version(self):self.assertEqual(self.sup.run(replace(self.d,contract_version='2')).status,Status.BLOCKED)
    def test_negative_budget(self):self.assertEqual(self.sup.run(replace(self.d,max_steps=0)).status,Status.BLOCKED)
    def test_negative_attempts(self):self.assertEqual(self.sup.run(replace(self.d,attempt_budget=0)).status,Status.BLOCKED)
    def test_zero_deadline(self):self.assertEqual(self.sup.run(replace(self.d,deadline_seconds=0)).status,Status.BLOCKED)
    def test_unauthorized_tool(self):self.assertEqual(self.sup.run(replace(self.d,allowed_tools=('write_data',))).status,Status.BLOCKED)
    def test_caller_scope(self):self.assertEqual(Supervisor(self.store,{'read_report'}).run(self.d).status,Status.BLOCKED)
    def test_side_effects(self):self.assertEqual(self.sup.run(replace(self.d,side_effects_allowed=True)).status,Status.BLOCKED)
    def test_missing_evidence(self):self.assertEqual(self.sup.run(replace(self.d,evidence_ids=())).status,Status.INSUFFICIENT_EVIDENCE)
    def test_unknown_id(self):self.assertEqual(self.sup.run(replace(self.d,evidence_ids=('bad',))).status,Status.FAILED)
    def test_worker_failure(self):self.assertEqual(self.sup.run(self.d,fail=True).status,Status.FAILED)
    def test_timeout_unknown(self):self.assertEqual(self.sup.run(self.d,simulated_timeout=True).status,Status.OUTCOME_UNKNOWN)
    def test_task_id_mismatch(self):self.assertEqual(self.sup.run(self.d,override_result=Result('wrong',Status.COMPLETED)).status,Status.FAILED)
    def test_forged_evidence(self):self.assertEqual(self.sup.run(self.d,override_result=Result('t1',Status.COMPLETED,(Finding('churn',999,('E-301',),'v1'),))).status,Status.FAILED)
    def test_empty_output(self):self.assertEqual(self.sup.run(self.d,override_result=Result('t1',Status.COMPLETED)).status,Status.INSUFFICIENT_EVIDENCE)
    def test_untrusted(self):self.assertEqual(Supervisor(EvidenceStore([Evidence('E-301','churn',40,'s',trusted=False)])).run(self.d).status,Status.FAILED)
    def test_duplicate_evidence_id(self):
        with self.assertRaises(ValueError):EvidenceStore(FIXTURES['mixed']*2)
    def test_source_version(self):self.assertFalse(self.store.verify(Finding('churn',40,('E-301',),'v2')))
    def test_incomplete(self):self.assertEqual(compare('incomplete')['supervisor']['status'],'insufficient_evidence')
    def test_churn_fixture(self):self.assertEqual(compare('churn')['supervisor']['status'],'completed')
    def test_pricing_fixture(self):self.assertEqual(compare('pricing')['supervisor']['status'],'completed')
    def test_mixed_fixture(self):self.assertEqual(compare('mixed')['supervisor']['status'],'completed')
    def test_staged_matches_baseline(self):self.assertEqual(run_workflow(FIXTURES['mixed'])['findings'],run_single(FIXTURES['mixed'])['findings'])
    def test_conflict_record(self):self.assertEqual(compare('conflict')['single']['findings']['churn'],-20)
    def test_aggregate_uncertain(self):self.assertEqual(self.sup.aggregate([Result('a',Status.OUTCOME_UNKNOWN)])['status'],'outcome_unknown')
    def test_aggregate_failed(self):self.assertEqual(self.sup.aggregate([Result('a',Status.FAILED)])['status'],'failed')
    def test_aggregate_missing(self):self.assertEqual(self.sup.aggregate([Result('a',Status.INSUFFICIENT_EVIDENCE)])['status'],'insufficient_evidence')
    def test_aggregate_conflict(self):
        a=Finding('churn',1,('E-301',),'v1');b=Finding('churn',2,('E-301',),'v1')
        self.assertEqual(self.sup.aggregate([Result('a',Status.COMPLETED,(a,)),Result('b',Status.COMPLETED,(b,))])['status'],'conflict')
    def test_zero_tool_allowance_denied_at_execution(self):
        self.assertEqual(self.sup.run(replace(self.d,allowed_tools=())).status, Status.BLOCKED)
    def test_read_only_without_calculate_denied(self):
        self.assertEqual(self.sup.run(replace(self.d,allowed_tools=('read_report',))).status,Status.BLOCKED)
    def test_worker_cannot_cite_undelegated_evidence(self):
        fake=Result('t1',Status.COMPLETED,(Finding('pricing',35,('E-302',),'v1'),))
        self.assertEqual(self.sup.run(self.d,override_result=fake).status,Status.FAILED)
    def test_worker_cannot_duplicate_evidence_ids(self):
        fake=Result('t1',Status.COMPLETED,(Finding('churn',80,('E-301','E-301'),'v1'),))
        self.assertEqual(self.sup.run(self.d,override_result=fake).status,Status.FAILED)
    def test_opposing_signed_values_flagged_even_with_pricing(self):
        from evidence import Evidence
        records=FIXTURES['conflict']+[Evidence('E-503','pricing',5,'pricing-report-v1')]
        sup=Supervisor(EvidenceStore(records))
        d=replace(self.d,evidence_ids=('E-501','E-502'))
        self.assertEqual(sup.run(d).status,Status.CONFLICT)
    def test_conflict_fixture_flagged(self):
        self.assertEqual(compare('conflict')['supervisor']['status'],'conflict')
    def test_workflow_executes_real_stage_functions(self):
        from workflow import extract,analyze,verify
        records=extract(FIXTURES['mixed'])
        self.assertEqual(verify(analyze(records)),'completed')
    def test_worker_stage_not_parallel(self):
        self.assertEqual(compare('mixed')['note'].startswith('Sequential'),True)
    def test_empty_correlation(self):self.assertEqual(self.sup.run(replace(self.d,correlation_id='')).status,Status.BLOCKED)
    def test_duplicate_tools(self):self.assertEqual(self.sup.run(replace(self.d,allowed_tools=('read_report','read_report'))).status,Status.BLOCKED)

if __name__=='__main__':unittest.main()
