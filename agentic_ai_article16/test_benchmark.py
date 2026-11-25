import unittest
from benchmark import DOCS, BY_ID, search, role_for
class TestControls(unittest.TestCase):
    def test_gold_not_preexposed_in_task(self):
        from benchmark import INSTRUCTION
        self.assertNotIn('D04',INSTRUCTION)
        self.assertNotIn('churn stayed flat',INSTRUCTION.lower())
    def test_shared_corpus(self): self.assertEqual(len(DOCS),len(BY_ID))
    def test_unique_documents(self): self.assertEqual(len(set(BY_ID)),len(DOCS))
    def test_search_result_limit(self): self.assertLessEqual(len(search('cohort reconciliation',5)),3)
    def test_search_determinism(self): self.assertEqual(search('churn',2),search('churn',2))
    def test_roles(self):
        for arch in ('single','workflow','supervisor'):
            self.assertEqual(len([role_for(arch,i) for i in range(6)]),6)
    def test_superseded_records_tagged(self): self.assertEqual(BY_ID['D01']['status'],'superseded')
    def test_gold_in_corpus(self): self.assertEqual(BY_ID['D04']['status'],'authoritative')

# Additional adversarial tests use scripted model responses: no live API calls.
from unittest.mock import patch
from benchmark import run_trial, score_final, request_parameters, Model, ProviderRequestError
import tempfile, os, csv, json, sys, urllib.error, io

class ScriptedModel:
    actions = []
    def __init__(self, name):
        self.total_tokens = 0
        self.model_calls = 0
        self.iter = iter(self.actions)
    def ask(self, prompt, max_tokens):
        self.model_calls += 1
        return next(self.iter)

class TestMalformedOutputs(unittest.TestCase):
    def trial(self, actions):
        class Fake(ScriptedModel):
            pass
        Fake.actions = actions
        with patch('benchmark.Model', Fake):
            return run_trial('single', 0, 'scripted')

    def test_null_citations_no_crash(self):
        r = self.trial([{'action':'read','id':'D04'}]*6 + [{'churn':'flat','drivers':['discounting','pricing mix'],'citations':None}])
        self.assertEqual(r['valid_citations'], 0)
        self.assertEqual(r['correct'], 0)

    def test_list_read_id_no_crash(self):
        r = self.trial([{'action':'read','id':['D04']}]*6 + [{'churn':'unknown','citations':[]}])
        self.assertEqual(r['failure'], '')
        self.assertEqual(r['tool_calls'], 6)
        self.assertEqual(r['correct'], 0)

    def test_negated_driver_keywords_cannot_pass(self):
        r = self.trial([{'action':'read','id':'D04'}]*6 + [{'churn':'flat','driver':'not discounting; pricing mix irrelevant','citations':['D04']}])
        self.assertEqual(r['accurate_driver'], 0)
        self.assertEqual(r['correct'], 0)

    def test_valid_explicit_drivers_pass(self):
        r = self.trial([{'action':'read','id':'D04'}]*6 + [{'churn':'flat','drivers':['discounting','pricing mix'],'citations':['D04']}])
        self.assertEqual(r['correct'], 1)

    def test_failed_provider_citation_accuracy_zero(self):
        class Broken(ScriptedModel):
            def ask(self, prompt, max_tokens):
                self.model_calls += 1
                raise ProviderRequestError('HTTP 400: {"error":"bad parameter"}')
        with patch('benchmark.Model', Broken):
            r = run_trial('single', 0, 'scripted')
        self.assertEqual(r['valid_citations'], 0)
        self.assertEqual(r['policy_compliant'], 0)
        self.assertIn('bad parameter', r['failure'])

    def test_unknown_without_citations_is_policy_compliant_but_not_valid_citations(self):
        r = self.trial([{'action':'search','query':'churn'}]*6 + [{'churn':'unknown','drivers':[],'citations':[]}])
        self.assertEqual(r['valid_citations'], 0)
        self.assertEqual(r['policy_compliant'], 1)

    def test_unread_citation_rejected(self):
        r = self.trial([{'action':'read','id':'D01'}]*6 + [{'churn':'flat','drivers':['discounting','pricing mix'],'citations':['D04']}])
        self.assertEqual(r['valid_citations'], 0)
        self.assertEqual(r['policy_compliant'], 0)

    def test_non_list_citations_rejected(self):
        r = self.trial([{'action':'read','id':'D04'}]*6 + [{'churn':'flat','drivers':['discounting','pricing mix'],'citations':'D04'}])
        self.assertEqual(r['valid_citations'], 0)
        self.assertEqual(r['policy_compliant'], 0)

    def test_model_request_parameter_selection(self):
        self.assertEqual(request_parameters('gpt-4.1-mini', 300), {'max_tokens':300,'temperature':0})
        self.assertEqual(request_parameters('gpt-5', 300), {'max_completion_tokens':300})
        self.assertEqual(request_parameters('o3-mini', 300), {'max_completion_tokens':300})

    def test_rerun_output_does_not_mix_trials(self):
        class Fake(ScriptedModel):
            actions = [{'action':'read','id':'D04'}]*6 + [{'churn':'flat','drivers':['discounting','pricing mix'],'citations':['D04']}]
        from benchmark import main
        with tempfile.TemporaryDirectory() as temp:
            for _ in range(2):
                with patch('benchmark.Model', Fake), patch.dict(os.environ, {'OPENAI_API_KEY':'local-fake'}), patch.object(sys, 'argv', ['benchmark.py','--trials','1','--output',temp]):
                    main()
                with open(os.path.join(temp,'summary.csv')) as f:
                    rows=list(csv.DictReader(f))
                with open(os.path.join(temp,'trials.jsonl')) as f:
                    traces=[json.loads(line) for line in f]
                self.assertEqual(len(rows),3)
                self.assertEqual(len(traces),3)

if __name__ == '__main__': unittest.main()
