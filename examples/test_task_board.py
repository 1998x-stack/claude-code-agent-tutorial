import unittest
from task_board import TaskBoard


class BoardTests(unittest.TestCase):
    def make_board(self):
        b = TaskBoard()
        b.add("inspect", "Read failing test")
        b.add("patch", "Make a minimal change", ("inspect",))
        b.add("verify", "Run tests", ("patch",))
        return b

    def test_dependency_and_state_flow(self):
        b = self.make_board()
        self.assertEqual(b.ready(), ["inspect"])
        with self.assertRaises(ValueError):
            b.start("patch")
        b.start("inspect")
        with self.assertRaises(ValueError):
            b.complete("inspect", "")
        b.complete("inspect", "Failure reproduced")
        self.assertEqual(b.ready(), ["patch"])
        b.start("patch")
        b.complete("patch", "Diff reviewed")
        b.start("verify")
        b.complete("verify", "Focused tests pass")
        self.assertTrue(all(t["status"] == "completed" for t in b.snapshot()))

    def test_cycle_and_unknown_reference(self):
        b = TaskBoard()
        b.add("a", "A", ("b",))
        b.add("b", "B", ("a",))
        with self.assertRaisesRegex(ValueError, "cycle"):
            b.validate()
        c = TaskBoard()
        c.add("x", "X", ("missing",))
        with self.assertRaisesRegex(ValueError, "unknown"):
            c.validate()

    def test_failure_is_terminal_not_completed(self):
        b = self.make_board()
        b.start("inspect")
        b.fail("inspect", "Insufficient access")
        self.assertEqual(b.tasks["inspect"].status, "failed")
        self.assertEqual(b.ready(), [])
        with self.assertRaises(ValueError):
            b.complete("inspect", "fake")

    def test_duplicate_and_active_limit(self):
        b = TaskBoard()
        b.add("one", "First")
        b.add("two", "Second")
        with self.assertRaises(ValueError):
            b.add("one", "Duplicate")
        b.start("one")
        with self.assertRaisesRegex(ValueError, "one in-progress"):
            b.start("two")


if __name__ == "__main__":
    unittest.main()
