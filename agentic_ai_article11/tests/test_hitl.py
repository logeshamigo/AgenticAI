import sqlite3
import tempfile
import concurrent.futures
import unittest
from pathlib import Path
from hitl import ApprovalController, InvalidTransition, PolicyDenied


class HITLTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.db"
        self.c = ApprovalController(self.path)
        self.c.seed_ticket("T-104", "acme")
        self.c.propose("R1", "acme", "T-104", "Resolved", "analyst-1", now=100, ttl_seconds=20)

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def test_pending_never_executes(self):
        self.assertEqual(self.c.execute("R1", now=101), "pending")
        self.assertEqual(self.c.writes(), 0)

    def test_approve_then_execute(self):
        self.assertEqual(self.c.review("R1", "reviewer-1", "approve", now=101), "approved")
        self.assertEqual(self.c.execute("R1", now=102), "verified")
        self.assertEqual(self.c.ticket("T-104")["status"], "Resolved")
        self.assertEqual(self.c.writes(), 1)

    def test_reject_blocks_action(self):
        self.assertEqual(self.c.review("R1", "reviewer-1", "reject", now=101), "rejected")
        self.assertEqual(self.c.execute("R1", now=102), "rejected")
        self.assertEqual(self.c.writes(), 0)

    def test_reviewer_wrong_tenant_scope(self):
        self.c.close()
        self.c = ApprovalController(self.path, {"reviewer-1": frozenset({"other"})})
        with self.assertRaises(PolicyDenied):
            self.c.review("R1", "reviewer-1", "approve", now=101)

    def test_unauthorized_reviewer(self):
        with self.assertRaises(PolicyDenied):
            self.c.review("R1", "outsider", "approve", now=101)
        self.assertEqual(self.c.get_request("R1")["status"], "pending")

    def test_requester_cannot_approve(self):
        self.c.close()
        self.c = ApprovalController(self.path, {"reviewer-1": frozenset({"acme"}), "analyst-1": frozenset({"acme"})})
        with self.assertRaises(PolicyDenied):
            self.c.review("R1", "analyst-1", "approve", now=101)

    def test_expires_before_review(self):
        self.assertEqual(self.c.review("R1", "reviewer-1", "approve", now=120), "expired")
        self.assertEqual(self.c.execute("R1", now=121), "expired")

    def test_approved_expires_before_execution(self):
        self.c.review("R1", "reviewer-1", "approve", now=101)
        self.assertEqual(self.c.execute("R1", now=120), "expired")
        self.assertEqual(self.c.writes(), 0)

    def test_old_version_invalidates_approval(self):
        self.c.review("R1", "reviewer-1", "approve", now=101)
        self.c.db.execute("UPDATE tickets SET version=version+1 WHERE ticket_id='T-104'")
        self.assertEqual(self.c.execute("R1", now=102), "stale")
        self.assertEqual(self.c.writes(), 0)

    def test_no_cross_tenant_ticket(self):
        with self.assertRaises(PolicyDenied):
            self.c.propose("R2", "other", "T-104", "Resolved", "analyst-1", now=101)

    def test_disallowed_target(self):
        with self.assertRaises(PolicyDenied):
            self.c.propose("R2", "acme", "T-104", "Closed", "analyst-1", now=101)

    def test_duplicate_request_id_fails(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.c.propose("R1", "acme", "T-104", "Resolved", "analyst-1", now=101)

    def test_double_review_fails(self):
        self.c.review("R1", "reviewer-1", "approve", now=101)
        with self.assertRaises(InvalidTransition):
            self.c.review("R1", "reviewer-1", "reject", now=102)

    def test_double_execute_no_duplicate(self):
        self.c.review("R1", "reviewer-1", "approve", now=101)
        self.c.execute("R1", now=102)
        self.assertEqual(self.c.execute("R1", now=103), "already_executed")
        self.assertEqual(self.c.writes(), 1)

    def test_post_commit_timeout_does_not_replay(self):
        self.c.review("R1", "reviewer-1", "approve", now=101)
        with self.assertRaises(TimeoutError):
            self.c.execute("R1", now=102, simulate_lost_response=True)
        self.assertEqual(self.c.execute("R1", now=103), "already_executed")
        self.assertEqual(self.c.writes(), 1)

    def test_recovery_after_restart(self):
        self.c.close()
        self.c = ApprovalController(self.path)
        self.assertEqual(self.c.get_request("R1")["status"], "pending")
        self.c.review("R1", "reviewer-1", "approve", now=101)
        self.assertEqual(self.c.execute("R1", now=102), "verified")

    def test_tampered_payload_digest_blocks_execution(self):
        self.c.review("R1", "reviewer-1", "approve", now=101)
        self.c.db.execute("UPDATE requests SET expected_version=2 WHERE request_id='R1'")
        with self.assertRaises(PolicyDenied):
            self.c.execute("R1", now=102)
        self.assertEqual(self.c.writes(), 0)

    def test_audit_events_recorded(self):
        self.c.review("R1", "reviewer-1", "reject", now=101)
        self.assertEqual(self.c.audit_events("R1"), ["proposed", "rejected"])

    def test_invalid_decision_denied(self):
        with self.assertRaises(PolicyDenied):
            self.c.review("R1", "reviewer-1", "later", now=101)

    def test_zero_ttl_denied(self):
        with self.assertRaises(PolicyDenied):
            self.c.propose("R2", "acme", "T-104", "Resolved", "analyst-1", now=101, ttl_seconds=0)


    def test_reviewer_permission_revoked_after_approval_is_blocked(self):
        self.c.review("R1", "reviewer-1", "approve", now=101)
        self.c.reviewer_scopes = {"reviewer-1": frozenset({"other"})}
        self.assertEqual(self.c.execute("R1", now=102), "blocked")
        self.assertEqual(self.c.writes(), 0)
        self.assertEqual(self.c.audit_events("R1"), ["proposed", "approved", "blocked"])

    def test_reviewed_action_hard_denial_revalidated_at_execution(self):
        self.c.review("R1", "reviewer-1", "approve", now=101)
        self.c.db.execute("UPDATE requests SET target='Closed' WHERE request_id='R1'")
        self.assertEqual(self.c.execute("R1", now=102), "blocked")
        self.assertEqual(self.c.ticket("T-104")["status"], "Open")

    def test_tampered_approver_is_blocked(self):
        self.c.review("R1", "reviewer-1", "approve", now=101)
        self.c.db.execute("UPDATE requests SET approved_by=NULL WHERE request_id='R1'")
        self.assertEqual(self.c.execute("R1", now=102), "blocked")
        self.assertEqual(self.c.writes(), 0)

    def test_blocked_cannot_be_resumed_without_new_proposal(self):
        self.c.review("R1", "reviewer-1", "approve", now=101)
        self.c.reviewer_scopes = {}
        self.assertEqual(self.c.execute("R1", now=102), "blocked")
        self.c.reviewer_scopes = {"reviewer-1": frozenset({"acme"})}
        self.assertEqual(self.c.execute("R1", now=103), "blocked")
        self.assertEqual(self.c.writes(), 0)

    def test_unauthorized_reviewer_never_logs_approval(self):
        with self.assertRaises(PolicyDenied):
            self.c.review("R1", "outsider", "approve", now=101)
        self.assertEqual(self.c.audit_events("R1"), ["proposed"])

    def test_concurrent_executions_commit_only_one_local_effect(self):
        self.c.review("R1", "reviewer-1", "approve", now=101)
        def run_one(_):
            c = ApprovalController(self.path)
            try:
                return c.execute("R1", now=102)
            finally:
                c.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run_one, range(2)))
        self.assertEqual(set(results), {"verified", "already_executed"})
        self.assertEqual(self.c.writes(), 1)

    def test_revoke_then_restart_still_blocked(self):
        self.c.review("R1", "reviewer-1", "approve", now=101)
        self.c.close()
        self.c = ApprovalController(self.path, reviewer_scopes={})
        self.assertEqual(self.c.execute("R1", now=102), "blocked")
        self.assertEqual(self.c.ticket("T-104")["status"], "Open")


    def test_pending_execute_after_ttl_persists_expiry(self):
        self.assertEqual(self.c.execute("R1", now=120), "expired")
        self.assertEqual(self.c.get_request("R1")["status"], "expired")
        self.assertEqual(self.c.audit_events("R1"), ["proposed", "expired"])
        self.assertEqual(self.c.writes(), 0)

    def test_expiry_sweep_expires_unattended_pending_request(self):
        self.assertEqual(self.c.expire_requests(now=119), 0)
        self.assertEqual(self.c.expire_requests(now=120), 1)
        self.assertEqual(self.c.get_request("R1")["status"], "expired")
        self.assertEqual(self.c.execute("R1", now=121), "expired")

    def test_expiry_sweep_expires_unexecuted_approval(self):
        self.c.review("R1", "reviewer-1", "approve", now=101)
        self.assertEqual(self.c.expire_requests(now=121), 1)
        self.assertEqual(self.c.get_request("R1")["status"], "expired")
        self.assertEqual(self.c.writes(), 0)

    def test_expiry_sweep_repeat_is_idempotent_after_restart(self):
        self.assertEqual(self.c.expire_requests(now=120), 1)
        self.assertEqual(self.c.expire_requests(now=125), 0)
        self.c.close()
        self.c = ApprovalController(self.path)
        self.assertEqual(self.c.expire_requests(now=150), 0)
        self.assertEqual(self.c.audit_events("R1"), ["proposed", "expired"])


if __name__ == "__main__":
    unittest.main()
