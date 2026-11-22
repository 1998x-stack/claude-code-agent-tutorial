import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from handoff_journal import Handoff, save, load


class HandoffJournalTests(unittest.TestCase):
    def fixture(self):
        return Handoff(
            task="Fix flaky parser test",
            constraints=("No production writes", "Use offline tests"),
            verified=("Failing assertion reproduced",),
            pending=("Inspect minimal fix", "Run test suite"),
            evidence_refs=("tests/test_parser.py:32",),
        )

    def test_roundtrip_preserves_constraints_and_pending(self):
        with TemporaryDirectory() as root:
            p = Path(root) / "handoff.json"
            digest = save(p, self.fixture())
            self.assertEqual(load(p, digest), self.fixture())
            self.assertEqual(digest, save(p, self.fixture()))

    def test_corruption_detected(self):
        with TemporaryDirectory() as root:
            p = Path(root) / "handoff.json"
            digest = save(p, self.fixture())
            p.write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                load(p, digest)

    def test_empty_constraints_and_progress_rejected(self):
        bad = Handoff("goal", (), ("observed",), ("todo",), ())
        with self.assertRaises(ValueError):
            bad.validate()
        bad2 = Handoff("goal", ("constraint",), (), (), ())
        with self.assertRaises(ValueError):
            bad2.validate()

    def test_symlink_destination_rejected(self):
        with TemporaryDirectory() as root:
            target = Path(root) / "real.json"
            target.write_text("do not change")
            link = Path(root) / "link.json"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                save(link, self.fixture())
            self.assertEqual(target.read_text(), "do not change")


if __name__ == "__main__":
    unittest.main()
