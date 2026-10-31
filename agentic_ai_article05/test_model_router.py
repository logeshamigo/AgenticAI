"""Run with `python -m unittest -v` from the package directory."""
import io
from contextlib import redirect_stdout
import unittest
from unittest.mock import patch
import model_router as m


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.source = m.AuthorizedFinancialSource()
        self.context = {"report_id": m.REPORT_ID, "account_id": m.ACCOUNT,
                        "data_class": m.DATA_CLASS, "context_chars": 1000}
        self.extract = dict(m.BASE_EXTRACTION)
        self.summary_context = {**self.context, "extract": self.extract,
                                "interpret": {"cause_status": "unverified"}}
        self.good_summary = {"source": "approved_warehouse", "cause_status": "unverified",
                             "change_pct": -8.0,
                             "summary": "Net revenue decreased 8.0%; cause not established."}

    def test_authorized_record_is_loaded_from_independent_source(self):
        self.assertEqual(self.source.fetch(m.REPORT_ID, m.ACCOUNT)["q2"], 920)

    def test_wrong_account_blocked_without_fallback(self):
        with self.assertRaises(m.PolicyViolation):
            self.source.fetch(m.REPORT_ID, "other-account")

    def test_correct_extract(self):
        m.validate("extract", self.extract, self.context, self.source)

    def test_bad_extraction_type(self):
        with self.assertRaisesRegex(m.InvalidOutput, "integers"):
            m.validate("extract", {**self.extract, "q1": "1000"}, self.context, self.source)

    def test_boolean_rejected_as_int(self):
        with self.assertRaisesRegex(m.InvalidOutput, "integers"):
            m.validate("extract", {**self.extract, "q1": True}, self.context, self.source)

    def test_schema_valid_but_wrong_q2(self):
        with self.assertRaisesRegex(m.InvalidOutput, "q2"):
            m.validate("extract", {**self.extract, "q2": 902}, self.context, self.source)

    def test_wrong_fiscal_period(self):
        with self.assertRaisesRegex(m.InvalidOutput, "fiscal_period"):
            m.validate("extract", {**self.extract, "fiscal_period": "FY2025-Q1_to_FY2025-Q2"}, self.context, self.source)

    def test_wrong_currency(self):
        with self.assertRaisesRegex(m.InvalidOutput, "currency"):
            m.validate("extract", {**self.extract, "currency": "EUR"}, self.context, self.source)

    def test_wrong_unit(self):
        with self.assertRaisesRegex(m.InvalidOutput, "unit"):
            m.validate("extract", {**self.extract, "unit": "millions"}, self.context, self.source)

    def test_wrong_metric(self):
        with self.assertRaisesRegex(m.InvalidOutput, "metric"):
            m.validate("extract", {**self.extract, "metric": "gross_revenue"}, self.context, self.source)

    def test_wrong_report_or_source(self):
        for field, val in (("report_id", "fabricated"), ("source", "unknown")):
            with self.subTest(field=field), self.assertRaisesRegex(m.InvalidOutput, field):
                m.validate("extract", {**self.extract, field: val}, self.context, self.source)

    def test_missing_or_extra_fields(self):
        bad = dict(self.extract)
        bad.pop("unit")
        for record in (bad, {**self.extract, "unexpected": 5}):
            with self.assertRaisesRegex(m.InvalidOutput, "Missing or unexpected"):
                m.validate("extract", record, self.context, self.source)

    def test_unverified_cause_remains_unverified(self):
        with self.assertRaisesRegex(m.InvalidOutput, "Root cause"):
            m.validate("interpret", {"cause_status":"verified", "reason":"promotions"},
                       self.context, self.source)

    def test_wrong_summary_numeric_field(self):
        with self.assertRaisesRegex(m.InvalidOutput, "Incorrect summary"):
            m.validate("summarize", {**self.good_summary, "change_pct": -50.0},
                       self.summary_context, self.source)

    def test_wrong_summary_prose_percentage(self):
        with self.assertRaisesRegex(m.InvalidOutput, "Unsupported percentage"):
            m.validate("summarize", {**self.good_summary,
              "summary": "Net revenue decreased 8.0%, then fell 50%; cause not established."},
              self.summary_context, self.source)

    def test_wrong_summary_direction(self):
        with self.assertRaisesRegex(m.InvalidOutput, "revenue trend"):
            m.validate("summarize", {**self.good_summary,
              "summary": "Net revenue increased 8.0%; cause not established."},
              self.summary_context, self.source)

    def test_unverified_causal_claim_in_prose(self):
        with self.assertRaisesRegex(m.InvalidOutput, "causal claim"):
            m.validate("summarize", {**self.good_summary,
              "summary": "Net revenue decreased 8.0% due to promotions; cause not established."},
              self.summary_context, self.source)

    def test_successful_good_summary(self):
        m.validate("summarize", self.good_summary, self.summary_context, self.source)

    def test_growth_and_flat_wording(self):
        self.assertIn("increased", m.format_summary(5.0))
        self.assertIn("unchanged", m.format_summary(0.0))
        self.assertIn("decreased", m.format_summary(-5.0))

    def test_policy_filter_data_class(self):
        p = m.PROFILES["small_structured"]
        self.assertFalse(m.eligible(p, "extract", "restricted_health", 1000))

    def test_policy_filter_capability_context_latency_and_quality(self):
        p = m.PROFILES["small_structured"]
        self.assertFalse(m.eligible(p, "summarize", m.DATA_CLASS, 1000))
        self.assertFalse(m.eligible(p, "extract", m.DATA_CLASS, 99999))
        self.assertFalse(m.eligible(p, "extract", m.DATA_CLASS, 1000, max_p95_ms=100))
        from dataclasses import replace
        self.assertFalse(m.eligible(replace(p, quality_approved=False), "extract", m.DATA_CLASS, 1000))
        self.assertFalse(m.eligible(replace(p, structured=False), "extract", m.DATA_CLASS, 1000))

    def test_no_eligible_model(self):
        with self.assertRaisesRegex(m.NoEligibleModel, "no eligible"):
            m.run_stage("extract", {**self.context,"data_class":"restricted_health"}, self.source)

    def test_exhausted_chain(self):
        def bad(*args):
            raise m.InvalidOutput("Always invalid")
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(m.NoValidOutput, "no valid permitted"):
            m.run_stage("extract", self.context, self.source, invoke=bad)

    def test_transient_is_retried_only_twice(self):
        calls = []
        def timeout(model, stage, context, attempt):
            calls.append((model, attempt))
            raise m.TransientProviderError("provider timeout")
        with redirect_stdout(io.StringIO()), self.assertRaises(m.NoValidOutput):
            m.run_stage("extract", self.context, self.source, invoke=timeout)
        self.assertEqual(len(calls), 3 * 2)

    def test_fallback_on_summarize_not_only_extract(self):
        with redirect_stdout(io.StringIO()) as output:
            value = m.run_stage("summarize", self.summary_context, self.source)
        self.assertEqual(value["change_pct"], -8.0)
        self.assertIn("rejected general", output.getvalue())
        self.assertIn("accepted general_backup", output.getvalue())

    def test_policy_violation_goes_to_controller(self):
        context = {**self.context, "account_id": "not-approved"}
        def good(model, stage, ctx, attempt):
            import json
            return json.dumps(self.extract)
        with redirect_stdout(io.StringIO()):
            state = m.decision_controller("extract", context, self.source, invoke=good)
        self.assertEqual(state["state"], "blocked")
        self.assertIn("not authorized", state["reason"])

    def test_exhausted_chain_goes_to_controller(self):
        def bad(*args):
            raise m.InvalidOutput("No valid response")
        with redirect_stdout(io.StringIO()):
            state = m.decision_controller("extract", self.context, self.source, invoke=bad)
        self.assertEqual(state["state"], "blocked")

    def test_full_run(self):
        with redirect_stdout(io.StringIO()) as output:
            value = m.run()
        self.assertEqual(value["state"], "completed")
        trace = output.getvalue()
        self.assertIn("Evidence mismatch: q2", trace)
        self.assertIn("transient general_backup attempt 1/2", trace)
        self.assertIn("rejected general", trace)
        self.assertIn("accepted general_backup", trace)
        self.assertIn("Decision Controller: completed", trace)


    # ---- Added in the revised package ----

    def test_evasive_causal_phrasings_rejected(self):
        # Each keeps the correct number and the "cause not established" phrase.
        for text in (
            "Net revenue decreased 8.0%; cause not established. Promotions drove the decline.",
            "Net revenue decreased 8.0%; cause not established. Pricing led to this, as a result of discounting.",
            "Net revenue decreased 8.0%, owing to promotions; cause not established.",
            "Net revenue decreased 8.0%; cause not established. Weak demand is the likely story.",
        ):
            with self.subTest(text=text), self.assertRaises(m.InvalidOutput):
                m.validate("summarize", {**self.good_summary, "summary": text},
                           self.summary_context, self.source)

    def test_spelled_out_percent_is_counted(self):
        with self.assertRaisesRegex(m.InvalidOutput, "Unsupported percentage"):
            m.validate("summarize", {**self.good_summary,
              "summary": "Net revenue decreased 8.0% and then fell 50 percent; cause not established."},
              self.summary_context, self.source)

    def test_only_approved_wording_is_accepted(self):
        with self.assertRaisesRegex(m.InvalidOutput, "approved evidence-derived wording"):
            m.validate("summarize", {**self.good_summary,
              "summary": "Net revenue decreased 8.0%; cause not established. Please escalate."},
              self.summary_context, self.source)

    def test_application_bug_is_not_blamed_on_models(self):
        # Missing context["extract"] is a programming error, not a model failure.
        with redirect_stdout(io.StringIO()), self.assertRaises(KeyError):
            m.run_stage("summarize", self.context, self.source)

    def test_ineligible_route_entry_is_never_invoked(self):
        import json
        from dataclasses import replace
        profiles = dict(m.PROFILES)
        profiles["small_structured"] = replace(profiles["small_structured"], quality_approved=False)
        calls = []
        def record(model, stage, ctx, attempt):
            calls.append(model)
            return json.dumps(self.extract)
        with redirect_stdout(io.StringIO()):
            m.run_stage("extract", self.context, self.source, invoke=record, profiles=profiles)
        self.assertNotIn("small_structured", calls)
        self.assertEqual(calls[0], "general_structured")

    def test_audit_trail_is_returned(self):
        with redirect_stdout(io.StringIO()):
            result = m.run()
        audit = result["audit"]
        self.assertIn(("extract", "small_structured", "invalid"), audit)
        self.assertIn(("extract", "general_backup", "transient"), audit)
        self.assertIn(("summarize", "general_backup", "accepted"), audit)

    def test_blocked_state_names_next_action(self):
        def bad(*args):
            raise m.InvalidOutput("No valid response")
        with redirect_stdout(io.StringIO()):
            state = m.decision_controller("extract", self.context, self.source, invoke=bad)
        self.assertEqual(state["action"], "stop_or_escalate")


    # ---- Added after the second review ----

    def test_unexpected_runtime_error_is_not_a_blocked_result(self):
        def buggy(*args):
            raise RuntimeError("bug: connection pool exhausted")
        with redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            m.decision_controller("extract", self.context, self.source, invoke=buggy)

    def test_router_failures_are_not_runtime_errors(self):
        self.assertFalse(issubclass(m.RouterFailure, RuntimeError))

    def test_causal_interpretation_rejected(self):
        for reason in ("Revenue fell due to promotions ending and weaker demand.",
                       "Churn of 12% drove the decline.",
                       "Weaker EMEA demand is the likely story."):
            with self.subTest(reason=reason), self.assertRaises(m.InvalidOutput):
                m.validate("interpret", {"cause_status": "unverified", "reason": reason},
                           self.context, self.source)

    def test_approved_interpretation_accepted(self):
        m.validate("interpret", {"cause_status": "unverified",
                                 "reason": m.APPROVED_INTERPRETATION}, self.context, self.source)

    def test_missing_data_class_fails_closed(self):
        ctx = {k: v for k, v in self.context.items() if k != "data_class"}
        with self.assertRaisesRegex(m.PolicyViolation, "Data classification missing"):
            m.run_stage("extract", ctx, self.source)

    def test_blank_or_missing_context_size_fails_closed(self):
        for bad in (None, 0, "1000"):
            with self.subTest(bad=bad), self.assertRaisesRegex(m.PolicyViolation, "Context size"):
                m.run_stage("extract", {**self.context, "context_chars": bad}, self.source)

    def test_missing_policy_input_reaches_controller_as_blocked(self):
        ctx = {k: v for k, v in self.context.items() if k != "data_class"}
        state = m.decision_controller("extract", ctx, self.source)
        self.assertEqual(state["state"], "blocked")
        self.assertIn("Data classification missing", state["reason"])


if __name__ == "__main__":
    unittest.main()
