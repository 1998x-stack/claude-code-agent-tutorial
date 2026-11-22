import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from long_running_contract import Feature, FeatureLedger

class LongRunningContractTests(unittest.TestCase):
    def make_ledger(self):
        return FeatureLedger("demo", "git:abc123", [
            Feature("feature-a", "Implement A", "A test passes"),
            Feature("feature-b", "Implement B", "B test passes"),
        ], max_attempts=2)

    def test_default_fail_requires_independent_evidence(self):
        ledger = self.make_ledger()
        self.assertFalse(ledger.complete)
        self.assertEqual(ledger.next_feature().ident, "feature-a")
        ledger.start("feature-a")
        with self.assertRaises(PermissionError):
            ledger.verify("feature-a", True, "model claims success", actor="generator")
        with self.assertRaises(ValueError):
            ledger.verify("feature-a", True, "", actor="evaluator")
        ledger.verify("feature-a", True, "unit tests: 5 passed", actor="evaluator")
        self.assertFalse(ledger.complete)
        ledger.start("feature-b")
        ledger.verify("feature-b", True, "browser QA: success", actor="evaluator")
        self.assertTrue(ledger.complete)

    def test_failed_checks_retry_then_block(self):
        ledger = self.make_ledger()
        ledger.start("feature-a")
        ledger.verify("feature-a", False, "unit test failure", actor="evaluator")
        self.assertEqual(ledger.next_feature().status, "pending")
        ledger.start("feature-a")
        ledger.verify("feature-a", False, "unit test failure", actor="evaluator")
        self.assertEqual(ledger._get("feature-a").status, "blocked")
        self.assertIsNone(ledger.next_feature())
        self.assertFalse(ledger.complete)

    def test_kill_switch_steering_are_human_only(self):
        ledger = self.make_ledger()
        with self.assertRaises(PermissionError):
            ledger.steer("switch scope", actor="model")
        ledger.steer("Prioritize feature B after A", actor="human")
        self.assertEqual(len(ledger.steering), 1)
        with self.assertRaises(PermissionError):
            ledger.stop(actor="model")
        ledger.stop(actor="human")
        with self.assertRaises(PermissionError):
            ledger.start("feature-a")
        with self.assertRaises(PermissionError):
            ledger.steer("continue", actor="human")
        self.assertFalse(ledger.complete)

    def test_checkpoint_integrity_revision_and_reload(self):
        ledger = self.make_ledger()
        ledger.start("feature-a")
        ledger.verify("feature-a", True, "proof-a", actor="evaluator")
        with TemporaryDirectory() as d:
            path = Path(d) / "features.json"
            digest = ledger.checkpoint(path)
            recovered = FeatureLedger.resume(path, digest, current_workspace_revision="git:abc123")
            self.assertEqual(recovered.next_feature().ident, "feature-b")
            self.assertEqual(recovered.features[0].evidence, "proof-a")
            with self.assertRaises(ValueError):
                FeatureLedger.resume(path, digest, current_workspace_revision="git:other")
            path.write_text(path.read_text().replace("proof-a", "fake-a"))
            with self.assertRaises(ValueError):
                FeatureLedger.resume(path, digest, current_workspace_revision="git:abc123")

    def test_traversal_in_feature_id_rejected(self):
        with self.assertRaises(ValueError):
            FeatureLedger("demo", "rev", [Feature("../secret", "a", "test")])
        with self.assertRaises(ValueError):
            FeatureLedger("demo", "rev", [Feature("a", "x", "y"), Feature("a", "x", "y")])

    def test_stale_claim_without_evaluator_not_stored(self):
        ledger = self.make_ledger()
        ledger.start("feature-a")
        with self.assertRaises(ValueError):
            ledger.verify("feature-a", "true", "fake report", actor="evaluator")
        self.assertEqual(ledger.features[0].status, "in_progress")

if __name__ == "__main__":
    unittest.main()
