import unittest
from permission_policy import Policy


class PermissionTests(unittest.TestCase):
    def test_deny_overrides_ask_allow_and_approval(self):
        p = Policy(deny=frozenset({"Write"}), ask=frozenset({"Write"}),
                   allow=frozenset({"Write"}))
        self.assertEqual(p.decide("Write", approved_by_user=True), "deny")

    def test_ask_precedes_allow_until_user_confirmation(self):
        p = Policy(ask=frozenset({"Edit"}), allow=frozenset({"Edit"}))
        self.assertEqual(p.decide("Edit"), "ask")
        self.assertEqual(p.decide("Edit", approved_by_user=True), "allow")

    def test_no_silent_permission_escalation(self):
        p = Policy(mode="read_only", allow=frozenset({"Read"}))
        self.assertEqual(p.decide("Read"), "allow")
        self.assertEqual(p.decide("Write", approved_by_user=True), "deny")
        self.assertEqual(p.decide("Bash"), "deny")
        p_ask = Policy(mode="read_only", ask=frozenset({"Write"}))
        self.assertEqual(p_ask.decide("Write", approved_by_user=True), "deny")

    def test_unattended_fails_closed(self):
        p = Policy(mode="unattended", ask=frozenset({"Edit"}),
                   allow=frozenset({"Read"}))
        self.assertEqual(p.decide("Edit", approved_by_user=True), "deny")
        self.assertEqual(p.decide("Write"), "deny")
        self.assertEqual(p.decide("Read"), "allow")


if __name__ == "__main__":
    unittest.main()
