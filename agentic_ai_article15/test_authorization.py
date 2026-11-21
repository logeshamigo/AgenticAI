from dataclasses import replace
import unittest

from demo import sample


class DelegatedAccessTests(unittest.TestCase):
    def setUp(self):
        self.api, self.request = sample()

    def assert_denied(self, reason, request=None, now=105):
        self.assertEqual(
            self.api.read(request or self.request, now=now), (None, reason)
        )

    def test_scoped_read_succeeds(self):
        self.assertEqual(self.api.read(self.request, now=105), (-4.0, "allowed"))

    def test_unknown_grant(self):
        self.assert_denied("unknown_grant", replace(self.request, grant_id="missing"))

    def test_actor_mismatch(self):
        self.assert_denied("actor_mismatch", replace(self.request, actor="coordinator"))

    def test_wrong_audience(self):
        grant_id = self.request.grant_id
        self.api.grants[grant_id] = replace(self.api.grants[grant_id], audience="a2a")
        self.assert_denied("wrong_audience")

    def test_expiry_boundary(self):
        self.assertEqual(self.api.read(self.request, now=109)[1], "allowed")
        self.assert_denied("expired", now=110)

    def test_revocation_after_success(self):
        self.assertEqual(self.api.read(self.request, now=105)[1], "allowed")
        self.api.revoked.add(self.request.grant_id)
        self.assert_denied("revoked", now=106)

    def test_wrong_workflow(self):
        self.assert_denied("wrong_workflow", replace(self.request, workflow="different"))

    def test_wrong_tenant(self):
        self.assert_denied("wrong_tenant", replace(self.request, tenant="enterprise-b"))

    def test_wrong_resource(self):
        self.assert_denied("wrong_resource", replace(self.request, resource="raw-invoices"))

    def test_wrong_action(self):
        self.assert_denied("wrong_action", replace(self.request, action="export"))

    def test_subject_access_removed(self):
        self.api.active_access.clear()
        self.assert_denied("subject_access_removed")

    def test_audit_names_subject_and_actor(self):
        self.api.read(self.request, now=105)
        entry = self.api.audit[-1]
        self.assertEqual(entry["subject"], "finance-analyst")
        self.assertEqual(entry["actor"], "pricing-specialist")
        self.assertEqual(entry["decision"], "allowed")


if __name__ == "__main__":
    unittest.main()
