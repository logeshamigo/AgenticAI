import json
import tempfile
import unittest
from pathlib import Path
from agent import Task, Controller, Checkpoints, PolicyDenied, VerificationFailed, OutcomeUnknown

class FakeUI:
    def __init__(self, status='Open', failure=None):
        self.status, self.failure, self.writes = status, failure, 0
    def observe(self, ticket_id): return self.status
    def submit(self, ticket_id, status):
        if self.failure == 'timeout_before_commit': raise TimeoutError()
        self.status = status
        self.writes += 1
        if self.failure == 'commit_then_timeout': raise TimeoutError()
        if self.failure == 'commit_then_unknown': raise OutcomeUnknown()
    def verify(self, ticket_id):
        if self.failure == 'verify_down': raise RuntimeError('down')
        return self.status

class TestController(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cp = Checkpoints(Path(self.temp.name) / 'state.json')
    def execute(self, fake, task=Task('T-104', 'Resolved', True), budget=1):
        return Controller(fake, self.cp, budget).run(task)
    def test_approval_required_no_write(self):
        f=FakeUI(); self.assertEqual(self.execute(f, Task('T-104', 'Resolved')), 'approval_required'); self.assertEqual(f.writes,0)
    def test_authorized_submission_verified(self):
        f=FakeUI(); self.assertEqual(self.execute(f), 'verified'); self.assertEqual(f.writes,1)
    def test_no_duplicate_when_already_done(self):
        f=FakeUI('Resolved'); self.assertEqual(self.execute(f), 'already_verified'); self.assertEqual(f.writes,0)
    def test_blocked_ticket(self):
        f=FakeUI(); self.assertRaises(PolicyDenied,self.execute,f,Task('T-999','Resolved',True)); self.assertEqual(f.writes,0)
    def test_blocked_status(self):
        f=FakeUI(); self.assertRaises(PolicyDenied,self.execute,f,Task('T-104','Delete',True)); self.assertEqual(f.writes,0)
    def test_budget_zero(self):
        f=FakeUI(); self.assertEqual(self.execute(f,budget=0),'stopped_budget'); self.assertEqual(f.writes,0)
    def test_commit_then_timeout_not_duplicated(self):
        f=FakeUI(failure='commit_then_timeout'); self.assertEqual(self.execute(f),'verified'); self.assertEqual(f.writes,1)
    def test_unknown_commit_not_duplicated(self):
        f=FakeUI(failure='commit_then_unknown'); self.assertEqual(self.execute(f),'verified'); self.assertEqual(f.writes,1)
    def test_timeout_before_commit_not_retried(self):
        f=FakeUI(failure='timeout_before_commit'); self.assertRaises(VerificationFailed,self.execute,f); self.assertEqual(f.writes,0)
    def test_verification_unavailable_no_retry(self):
        f=FakeUI(failure='verify_down'); self.assertRaises(VerificationFailed,self.execute,f); self.assertEqual(f.writes,1)
    def test_checkpoint_records_without_page_content(self):
        self.execute(FakeUI()); text=self.cp.filename.read_text(); self.assertEqual(json.loads(text)['events'][-1]['stage'],'verified'); self.assertNotIn('Ignore all previous instructions',text)
    def test_recovery_after_prior_commit_on_new_run(self):
        f=FakeUI(failure='commit_then_timeout'); self.assertEqual(self.execute(f),'verified'); self.assertEqual(self.execute(f),'already_verified'); self.assertEqual(f.writes,1)

if __name__ == '__main__': unittest.main()
