import unittest
from delegation_contract import Delegation, Finding, delegate, validate_result


class DelegationTests(unittest.TestCase):
    def test_child_cannot_escalate_tool_scope(self):
        with self.assertRaises(PermissionError):
            delegate(name="review", goal="Review test",
                     refs=("test.py",), parent_allowed=frozenset({"Read"}),
                     requested_tools=frozenset({"Read", "Write"}), budget=3)

    def test_explicit_task_and_evidence(self):
        job = delegate(name="review", goal="Find failing assertion",
                       refs=("test.py", "src.py"),
                       parent_allowed=frozenset({"Read", "Grep"}),
                       requested_tools=frozenset({"Read"}), budget=4)
        self.assertEqual(job.allowed_tools, frozenset({"Read"}))
        validate_result(job, Finding("review", "Found the assertion",
                                      ("test.py",), ("needs runtime check",)))
        with self.assertRaises(ValueError):
            validate_result(job, Finding("review", "Guess",
                                         ("private.env",), ()))

    def test_rejects_unbounded_or_underspecified_job(self):
        common = dict(name="inspect", goal="Inspect", refs=("src.py",),
                      parent_allowed=frozenset({"Read"}),
                      requested_tools=frozenset({"Read"}))
        with self.assertRaises(ValueError):
            delegate(**common, budget=0)
        with self.assertRaises(ValueError):
            delegate(**{**common, "refs": ()}, budget=3)


if __name__ == "__main__":
    unittest.main()
