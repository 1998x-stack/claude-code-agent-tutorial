import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from long_running_contract import Feature, FeatureLedger, MAX_CHECKPOINT_BYTES


class LongRunningContractTests(unittest.TestCase):
    def make_ledger(self):
        return FeatureLedger("demo", "git:abc123", [
            Feature("feature-a", "Implement A", "A test passes"),
            Feature("feature-b", "Implement B", "B test passes"),
        ], max_attempts=2)

    def test_default_fail_requires_external_verdict_and_reference(self):
        ledger = self.make_ledger()
        self.assertFalse(ledger.complete)
        self.assertEqual(ledger.next_feature().ident, "feature-a")
        ledger.start("feature-a")
        with self.assertRaises(PermissionError):
            ledger.verify("feature-a", True, "model claims success", actor="generator")
        with self.assertRaises(ValueError):
            ledger.verify("feature-a", True, "", actor="evaluator")
        ledger.verify("feature-a", True, "report://unit-tests/sha256:abc", actor="evaluator")
        self.assertFalse(ledger.complete)
        ledger.start("feature-b")
        ledger.verify("feature-b", True, "report://browser/sha256:def", actor="evaluator")
        self.assertTrue(ledger.complete)

    def test_failed_checks_retry_then_block_project(self):
        ledger = self.make_ledger()
        ledger.start("feature-a")
        ledger.verify("feature-a", False, "report://failed-attempt-1", actor="evaluator")
        self.assertEqual(ledger.next_feature().status, "pending")
        ledger.start("feature-a")
        ledger.verify("feature-a", False, "report://failed-attempt-2", actor="evaluator")
        self.assertEqual(ledger._get("feature-a").status, "blocked")
        self.assertIsNone(ledger.next_feature())
        with self.assertRaises(RuntimeError):
            ledger.start("feature-b")
        self.assertFalse(ledger.complete)

    def test_resume_of_in_progress_feature_does_not_consume_attempt(self):
        ledger = self.make_ledger()
        ledger.start("feature-a")
        before_attempts, before_version = ledger.features[0].attempts, ledger.version
        ledger.start("feature-a")
        self.assertEqual(ledger.features[0].attempts, before_attempts)
        self.assertEqual(ledger.version, before_version)
        with TemporaryDirectory() as d:
            path = Path(d) / "features.json"
            digest = ledger.checkpoint(path)
            recovered = FeatureLedger.resume(path, digest, current_workspace_revision="git:abc123")
            recovered.start("feature-a")
            self.assertEqual(recovered.features[0].attempts, 1)

    def test_kill_switch_is_idempotent_and_steering_is_only_a_note(self):
        ledger = self.make_ledger()
        original_order = [f.ident for f in ledger.features]
        with self.assertRaises(PermissionError):
            ledger.steer("change priority", actor="model")
        ledger.steer("Prioritize feature B after A", actor="human")
        self.assertEqual([f.ident for f in ledger.features], original_order)
        self.assertEqual(len(ledger.steering), 1)
        with self.assertRaises(PermissionError):
            ledger.stop(actor="model")
        ledger.stop(actor="human")
        version = ledger.version
        ledger.stop(actor="human")
        self.assertEqual(ledger.version, version)
        with self.assertRaises(PermissionError):
            ledger.start("feature-a")
        with self.assertRaises(PermissionError):
            ledger.steer("continue", actor="human")
        self.assertFalse(ledger.complete)

    def test_checkpoint_integrity_revision_and_reload(self):
        ledger = self.make_ledger()
        ledger.start("feature-a")
        ledger.verify("feature-a", True, "report://proof-a", actor="evaluator")
        with TemporaryDirectory() as d:
            path = Path(d) / "features.json"
            digest = ledger.checkpoint(path)
            recovered = FeatureLedger.resume(path, digest, current_workspace_revision="git:abc123")
            self.assertEqual(recovered.next_feature().ident, "feature-b")
            self.assertEqual(recovered.features[0].evidence, "report://proof-a")
            with self.assertRaises(ValueError):
                FeatureLedger.resume(path, digest, current_workspace_revision="git:other")
            path.write_text(path.read_text().replace("proof-a", "fake-a"), encoding="utf-8")
            with self.assertRaises(ValueError):
                FeatureLedger.resume(path, digest, current_workspace_revision="git:abc123")

    def test_duplicate_json_keys_are_rejected(self):
        raw = b'{"schema":1,"schema":1,"ledger":{}}'
        with TemporaryDirectory() as d:
            path = Path(d) / "bad.json"
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                FeatureLedger.resume(path, hashlib.sha256(raw).hexdigest(),
                                     current_workspace_revision="rev")

    def test_large_checkpoint_is_rejected_before_unbounded_read(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "large.json"
            path.write_bytes(b"x" * (MAX_CHECKPOINT_BYTES + 1))
            with self.assertRaises(ValueError):
                FeatureLedger.resume(path, "0" * 64, current_workspace_revision="rev")

    def test_strict_types_reject_bool_and_malformed_rows(self):
        with self.assertRaises(ValueError):
            FeatureLedger("demo", "rev", [Feature("a", "x", "y")], max_attempts=True)
        with self.assertRaises(ValueError):
            FeatureLedger("demo", "rev", [Feature("a", "x", "y", attempts=True)])
        with self.assertRaises(ValueError):
            FeatureLedger("demo", "rev", [Feature("a", "x", "y", status="in_progress")])
        ledger = self.make_ledger()
        ledger.start("feature-a")
        with self.assertRaises(ValueError):
            ledger.verify("feature-a", 1, "fake", actor="evaluator")
        with self.assertRaises(ValueError):
            ledger.verify("feature-a", True, 123, actor="evaluator")

    def test_traversal_and_duplicate_feature_ids_rejected(self):
        with self.assertRaises(ValueError):
            FeatureLedger("demo", "rev", [Feature("../secret", "a", "test")])
        with self.assertRaises(ValueError):
            FeatureLedger("demo", "rev", [Feature("a", "x", "y"), Feature("a", "x", "y")])

    def test_checkpoint_rejects_destination_symlink(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            target = root / "real.json"
            target.write_text("original", encoding="utf-8")
            link = root / "link.json"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are unavailable on this platform")
            with self.assertRaises(ValueError):
                self.make_ledger().checkpoint(link)


if __name__ == "__main__":
    unittest.main()
