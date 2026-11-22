import unittest
from permission_gateway import Approval, PermissionGateway, ToolRequest
from permission_policy import Policy


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.gate = PermissionGateway(Policy(ask=frozenset({"Edit"})))
        self.req = ToolRequest("Edit", {"path": "docs/a.md", "content": "hello"})

    def token(self, req=None):
        req = req or self.req
        return Approval(req.fingerprint(), "user", "approve")

    def test_missing_approval_requires_prompt(self):
        self.assertEqual(self.gate.evaluate(self.req)[0], "ask")

    def test_exact_request_and_one_time_replay(self):
        self.assertEqual(self.gate.evaluate(self.req, self.token())[0], "allow")
        self.assertEqual(self.gate.evaluate(self.req, self.token())[0], "deny")
        changed = ToolRequest("Edit", {"path": "docs/b.md", "content": "hello"})
        self.assertEqual(self.gate.evaluate(changed, self.token())[0], "deny")

    def test_denial_overrides_confirmation(self):
        gate = PermissionGateway(Policy(deny=frozenset({"Edit"}), ask=frozenset({"Edit"})))
        self.assertEqual(gate.evaluate(self.req, self.token())[0], "deny")

    def test_refused_and_missing_identity(self):
        self.assertEqual(self.gate.evaluate(
            self.req, Approval(self.req.fingerprint(), "user", "deny"))[0], "deny")
        self.assertEqual(self.gate.evaluate(
            self.req, Approval(self.req.fingerprint(), "", "approve"))[0], "deny")

    def test_model_supplied_approval_not_used(self):
        req = ToolRequest("Edit", {"path": "a.md", "approved": True})
        self.assertEqual(self.gate.evaluate(req)[0], "ask")

    def test_unknown_tool_and_malformed_request_are_denied(self):
        self.assertEqual(self.gate.evaluate(ToolRequest("RootShell", {}))[0], "deny")
        self.assertEqual(self.gate.evaluate(object())[0], "deny")
        with self.assertRaises(ValueError):
            ToolRequest("Edit", {"score": float("nan")}).fingerprint()


if __name__ == "__main__":
    unittest.main()
