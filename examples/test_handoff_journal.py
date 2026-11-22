import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from handoff_journal import Handoff, save, load, MAX_JOURNAL_BYTES


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

    def test_empty_and_malformed_fields_rejected(self):
        with self.assertRaises(ValueError):
            Handoff("goal", (), ("observed",), ("todo",), ()).validate()
        with self.assertRaises(ValueError):
            Handoff("goal", ("constraint",), (), (), ()).validate()
        with self.assertRaises(ValueError):
            Handoff("goal", ("constraint",), (), ("todo",), ("",)).validate()
        with self.assertRaises(ValueError):
            Handoff("goal", ["constraint"], (), ("todo",), ()).validate()

    def test_symlink_destination_rejected(self):
        with TemporaryDirectory() as root:
            target = Path(root) / "real.json"
            target.write_text("do not change")
            link = Path(root) / "link.json"
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                save(link, self.fixture())
            self.assertEqual(target.read_text(), "do not change")

    def test_duplicate_json_keys_and_bad_digest_rejected(self):
        raw = b'{"schema":1,"schema":1,"handoff":{}}'
        with TemporaryDirectory() as root:
            path = Path(root) / "duplicate.json"
            path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                load(path, digest)
            with self.assertRaises(ValueError):
                load(path, "not-a-digest")

    def test_oversized_journal_rejected_before_unbounded_read(self):
        with TemporaryDirectory() as root:
            path = Path(root) / "large.json"
            path.write_bytes(b"x" * (MAX_JOURNAL_BYTES + 1))
            with self.assertRaises(ValueError):
                load(path, "0" * 64)


if __name__ == "__main__":
    unittest.main()
