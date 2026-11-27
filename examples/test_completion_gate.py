import unittest
from completion_gate import CheckEvidence, CompletionGate, EvaluatorLoop, TaskContract


class CompletionGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = CompletionGate(TaskContract(
            ("tests", "review"), max_steps=3, requires_human_approval=True
        ))

    def test_model_claim_is_not_a_completion_signal(self):
        self.assertEqual(self.gate.decide(), "continue")

    def test_evidence_and_human_approval_are_required(self):
        self.gate.record_check("tests", True, "pytest: 12 passed")
        self.gate.record_check("review", True, "diff reviewed")
        self.assertEqual(self.gate.decide(), "await_approval")
        with self.assertRaises(PermissionError):
            self.gate.record_human_decision(True, "model")
        self.gate.record_human_decision(True, "human")
        self.assertEqual(self.gate.decide(), "ready")

    def test_failed_or_unverifiable_check_blocks_readiness(self):
        with self.assertRaises(ValueError):
            self.gate.record_check("tests", True, "")
        self.gate.record_check("tests", False, "pytest: 1 failed")
        self.gate.record_check("review", True, "review log")
        self.assertEqual(self.gate.decide(), "continue")

    def test_denial_and_step_budget_fail_closed(self):
        self.gate.record_human_decision(False, "human")
        self.assertEqual(self.gate.decide(), "blocked")
        with self.assertRaises(RuntimeError):
            self.gate.record_step()
        other = CompletionGate(TaskContract(("tests",), max_steps=1))
        other.record_step()
        self.assertEqual(other.decide(), "budget_exhausted")
        with self.assertRaises(RuntimeError):
            other.record_step()

    def test_unknown_check_rejected(self):
        with self.assertRaises(ValueError):
            self.gate.record_check("deploy_prod", True, "done")

    def test_boolean_strings_and_non_finite_scores_rejected(self):
        with self.assertRaises(ValueError):
            self.gate.record_check("tests", "false", "looks okay")
        with self.assertRaises(ValueError):
            self.gate.record_human_decision("false", "human")
        with self.assertRaises(ValueError):
            CheckEvidence(1, "fake proof")
        with self.assertRaises(ValueError):
            TaskContract(("tests",), max_steps=True)
        with self.assertRaises(ValueError):
            EvaluatorLoop(threshold=True, max_rounds=2)
        loop = EvaluatorLoop(threshold=.8, max_rounds=2)
        for invalid in (True, float("nan"), float("inf"), -0.1, 1.1):
            with self.assertRaises(ValueError):
                loop.record(invalid)

    def test_evaluator_optimizer_is_bounded(self):
        loop = EvaluatorLoop(threshold=.8, max_rounds=2)
        self.assertEqual(loop.record(.5), "continue")
        self.assertEqual(loop.record(.75), "budget_exhausted")
        with self.assertRaises(RuntimeError):
            loop.record(.9)
        good = EvaluatorLoop(threshold=.8, max_rounds=3)
        self.assertEqual(good.record(.9), "accepted")


if __name__ == "__main__":
    unittest.main()
