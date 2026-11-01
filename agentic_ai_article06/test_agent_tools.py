"""Deterministic unit and concurrent integration tests for the Article 06 demo."""
import json
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import time
import unittest

from agent_tools import (
    Approval, CommitThenLoseResponse, FISCAL_PERIOD, READ_TOOL, REASON,
    REPORT_ID, WRITE_TOOL, ReportSource, TicketStore, ToolDispatcher,
    TrustedContext, WorkflowBudget, approval_for, change_percent,
    operation_key, payload_digest, sample_context,
)

READ_ARGS = {"report_id": REPORT_ID, "fiscal_period": FISCAL_PERIOD}
WRITE_ARGS = {**READ_ARGS, "reason": REASON}


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = TicketStore(str(Path(self.tmp.name) / "test.sqlite3"))
        self.dispatcher = ToolDispatcher(ReportSource(), self.store, sleep=lambda _: None, jitter=lambda: 0)

    def call(self, name, payload, ctx=None, step=None, dispatcher=None):
        return (dispatcher or self.dispatcher).dispatch(name, json.dumps(payload), ctx or sample_context(),
                                                         step or ("read-quarterly" if name == READ_TOOL else "review-quarterly"))

    def test_01_read_success_and_computation(self):
        r = self.call(READ_TOOL, READ_ARGS)
        self.assertEqual(r.status, "ok")
        self.assertEqual(change_percent(r.data), -8.0)

    def test_02_unknown_tool_denied(self):
        self.assertEqual(self.call("send_email", {}).status, "blocked")

    def test_03_tool_not_on_context_allowlist(self):
        ctx = sample_context()
        ctx = TrustedContext(ctx.tenant_id, ctx.workflow_id, ctx.allowed_report_ids,
                             ctx.allowed_period, frozenset({WRITE_TOOL}), ctx.approvals)
        self.assertEqual(self.call(READ_TOOL, READ_ARGS, ctx).status, "blocked")

    def test_04_unexpected_field_denied(self):
        self.assertEqual(self.call(READ_TOOL, {**READ_ARGS, "approved": True}).status, "invalid")

    def test_05_duplicate_json_key_denied(self):
        raw = '{"report_id":"%s","report_id":"x","fiscal_period":"%s"}' % (REPORT_ID, FISCAL_PERIOD)
        self.assertEqual(self.dispatcher.dispatch(READ_TOOL, raw, sample_context(), "read-quarterly").status, "invalid")

    def test_06_unauthorized_report_denied(self):
        self.assertEqual(self.call(READ_TOOL, {**READ_ARGS, "report_id": "secret-report"}).status, "blocked")

    def test_07_fiscal_period_semantic_mismatch_denied(self):
        self.assertEqual(self.call(READ_TOOL, {**READ_ARGS, "fiscal_period": "FY2025-Q1-Q2"}).status, "blocked")

    def test_08_source_tenant_defense_in_depth(self):
        d = ToolDispatcher(ReportSource(tenant_id="another-tenant"), self.store)
        self.assertEqual(self.call(READ_TOOL, READ_ARGS, dispatcher=d).status, "blocked")

    def test_09_source_period_defense_in_depth(self):
        d = ToolDispatcher(ReportSource(period="FY2025-Q1-Q2"), self.store)
        self.assertEqual(self.call(READ_TOOL, READ_ARGS, dispatcher=d).status, "blocked")

    def test_10_provenance_and_sensitive_source_fields_stripped(self):
        r = self.call(READ_TOOL, READ_ARGS)
        self.assertEqual(r.data["source"], "finance_fixture:get_financial_report")
        self.assertEqual(r.data["trust"], "untrusted_external")
        self.assertNotIn("tenant_id", str(r.data))
        self.assertNotIn("internal_account_token", str(r.data))
        self.assertNotIn("IGNORE PREVIOUS INSTRUCTIONS", str(r.data))
        self.assertEqual(set(r.data["content"]), {"report_id", "fiscal_period", "currency", "unit",
                                                 "q1_net_revenue", "q2_net_revenue"})

    def test_11_transient_read_retried(self):
        d = ToolDispatcher(ReportSource(fail_first=True), self.store, sleep=lambda _: None, jitter=lambda: 0)
        r = self.call(READ_TOOL, READ_ARGS, dispatcher=d)
        self.assertEqual((r.status, r.attempts), ("ok", 2))
        self.assertEqual(d.budget.backend_attempts, 2)

    def test_12_transient_read_exhaustion(self):
        d = ToolDispatcher(ReportSource(fail_first=True), self.store, max_read_attempts=1)
        self.assertEqual(self.call(READ_TOOL, READ_ARGS, dispatcher=d).status, "retry_exhausted")

    def test_13_write_without_approval_blocked(self):
        self.assertEqual(self.call(WRITE_TOOL, WRITE_ARGS).status, "blocked")
        self.assertEqual(self.store.count(), 0)

    def test_14_approved_write_succeeds(self):
        self.assertTrue(self.call(WRITE_TOOL, WRITE_ARGS, sample_context(approved=True)).data["content"]["created"])

    def test_15_changed_reason_blocked_with_approval_bound_to_hash(self):
        changed = {**WRITE_ARGS, "reason": "Different approved-looking reason"}
        self.assertEqual(self.call(WRITE_TOOL, changed, sample_context(approved=True)).status, "blocked")
        self.assertEqual(self.store.count(), 0)

    def test_16_real_post_commit_response_loss_then_replay_same_step(self):
        d = ToolDispatcher(ReportSource(), CommitThenLoseResponse(self.store))
        first = self.call(WRITE_TOOL, WRITE_ARGS, sample_context(approved=True), dispatcher=d)
        self.assertEqual(first.status, "uncertain")
        self.assertEqual(self.store.count(), 1)  # commit really occurred before lost response
        second = self.call(WRITE_TOOL, WRITE_ARGS, sample_context(approved=True), dispatcher=d)
        self.assertEqual(second.status, "ok")
        self.assertFalse(second.data["content"]["created"])
        self.assertEqual(self.store.count(), 1)

    def test_17_same_operation_id_different_payload_rejected_at_store(self):
        key = operation_key("flow", "step")
        self.store.create(key, payload_digest(WRITE_ARGS), "acme", REPORT_ID, REASON)
        with self.assertRaisesRegex(Exception, "conflicting payload"):
            self.store.create(key, payload_digest({**WRITE_ARGS, "reason": "new"}), "acme", REPORT_ID, "new")

    def test_18_delimiter_collision_is_impossible_for_given_example(self):
        self.assertNotEqual(operation_key("a:b", "c"), operation_key("a", "b:c"))

    def test_19_workflow_budget_blocks_model_reproposals(self):
        budget = WorkflowBudget(max_step_dispatches=2)
        d = ToolDispatcher(ReportSource(), self.store, budget)
        self.assertEqual(self.call(READ_TOOL, READ_ARGS, dispatcher=d).status, "ok")
        self.assertEqual(self.call(READ_TOOL, READ_ARGS, dispatcher=d).status, "ok")
        self.assertEqual(self.call(READ_TOOL, READ_ARGS, dispatcher=d).status, "blocked")

    def test_20_total_backend_budget_counts_read_retries(self):
        d = ToolDispatcher(ReportSource(fail_first=True), self.store,
                           WorkflowBudget(max_backend_attempts=1), sleep=lambda _: None, jitter=lambda: 0)
        self.assertEqual(self.call(READ_TOOL, READ_ARGS, dispatcher=d).status, "blocked")

    def test_21_deadline_denies_call(self):
        d = ToolDispatcher(ReportSource(), self.store, WorkflowBudget(deadline=time.monotonic()-1))
        self.assertEqual(self.call(READ_TOOL, READ_ARGS, dispatcher=d).status, "blocked")

    def test_22_injected_sleep_hook_invoked(self):
        waits=[]
        d = ToolDispatcher(ReportSource(fail_first=True), self.store, sleep=waits.append, jitter=lambda: 0)
        self.call(READ_TOOL, READ_ARGS, dispatcher=d)
        self.assertEqual(waits, [0.01])

    def test_23_concurrent_ten_writers_same_op_produce_one_row(self):
        key = operation_key("c-flow", "c-step")
        req = payload_digest(WRITE_ARGS)
        def once(_):
            return self.store.create(key, req, "acme", REPORT_ID, REASON)
        with ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(once, range(10)))
        self.assertEqual(sum(r["created"] for r in results), 1)
        self.assertEqual(self.store.count(), 1)
        self.assertEqual(len({r["ticket_id"] for r in results}), 1)

    def test_24_write_result_provenance(self):
        r = self.call(WRITE_TOOL, WRITE_ARGS, sample_context(approved=True))
        self.assertEqual(set(r.data), {"source", "trust", "content"})
        self.assertEqual(r.data["source"], "local_sqlite:create_review_ticket")

    def test_25_wrong_args_type_denied(self):
        self.assertEqual(self.call(READ_TOOL, {**READ_ARGS, "report_id": 3}).status, "invalid")


if __name__ == "__main__":
    unittest.main(verbosity=2)
