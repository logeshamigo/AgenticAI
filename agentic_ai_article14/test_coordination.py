from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from coordination import ContractConflict, Coordinator, Specialist


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        self.path = root / "coordinator.db"
        self.coordinator = Coordinator(self.path)
        self.specialist_path = root / "specialist.db"
        self.specialist = Specialist(self.specialist_path)
        self.coordinator.prepare("pricing", "Q3 renewals", 100)

    def dispatch(self):
        self.coordinator.dispatch(self.specialist, "pricing", 90)
        return self.coordinator.state("pricing")["task_id"]

    def complete(self, observed_at):
        task_id = self.dispatch()
        snapshot = self.specialist.finish(task_id, "finding")
        self.coordinator.observe("pricing", snapshot, observed_at)
        return snapshot

    def test_lost_ack_recovers_existing_task_after_both_reopen_databases(self):
        with self.assertRaises(TimeoutError):
            self.coordinator.dispatch(self.specialist, "pricing", 80, lose_ack=True)
        self.assertIsNone(self.coordinator.state("pricing")["task_id"])
        self.coordinator = Coordinator(self.path)
        self.specialist = Specialist(self.specialist_path)
        self.assertEqual(self.dispatch(), 1)
        self.assertEqual(self.specialist.submit("next-key", "Other task").task_id, 2)

    def test_receiver_rejects_changed_request_for_same_key(self):
        self.dispatch()
        with self.assertRaises(ContractConflict):
            self.specialist.submit("pricing", "Q4 renewals")

    def test_coordinator_rejects_changed_deadline_for_same_key(self):
        with self.assertRaises(ContractConflict):
            self.coordinator.prepare("pricing", "Q3 renewals", 110)

    def test_completion_before_cutoff_is_adopted(self):
        self.complete(99)
        self.assertEqual(self.coordinator.state("pricing")["adopted_finding"], "finding")

    def test_completion_exactly_at_cutoff_is_retained_but_excluded(self):
        self.complete(100)
        state = self.coordinator.state("pricing")
        self.assertEqual((state["remote_status"], state["remote_finding"]), ("completed", "finding"))
        self.assertIsNone(state["adopted_finding"])

    def test_finalized_report_excludes_completion_even_before_cutoff(self):
        self.coordinator.finalize("pricing")
        self.complete(99)
        self.assertIsNone(self.coordinator.state("pricing")["adopted_finding"])

    def test_duplicate_completion_preserves_original_adoption(self):
        snapshot = self.complete(99)
        self.assertEqual(self.coordinator.observe("pricing", snapshot, 105), "duplicate")
        self.assertEqual(self.coordinator.state("pricing")["adopted_finding"], "finding")

    def test_stale_working_update_after_completion_is_ignored(self):
        snapshot = self.complete(99)
        older = replace(snapshot, revision=1, status="working", finding=None)
        self.assertEqual(self.coordinator.observe("pricing", older, 101), "stale")
        self.assertEqual(self.coordinator.state("pricing")["remote_status"], "completed")

    def test_same_revision_with_changed_result_is_rejected(self):
        snapshot = self.complete(99)
        with self.assertRaises(ContractConflict):
            self.coordinator.observe("pricing", replace(snapshot, finding="changed"), 99)

    def test_completion_can_win_cancellation_race(self):
        task_id = self.dispatch()
        self.specialist.finish(task_id, "finding")
        self.coordinator.request_cancel(self.specialist, "pricing", 101)
        state = self.coordinator.state("pricing")
        self.assertEqual((state["cancel_requested"], state["remote_status"]), (1, "completed"))
        self.assertIsNone(state["adopted_finding"])

    def test_cancellation_can_win_completion_race(self):
        task_id = self.dispatch()
        self.coordinator.request_cancel(self.specialist, "pricing", 98)
        self.assertEqual(self.specialist.finish(task_id, "finding").status, "canceled")
        self.assertIsNone(self.coordinator.state("pricing")["adopted_finding"])

    def test_mismatched_remote_task_is_rejected(self):
        self.dispatch()
        other = self.specialist.submit("other", "Different task")
        with self.assertRaises(ContractConflict):
            self.coordinator.observe("pricing", other, 99)
