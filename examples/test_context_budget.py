import unittest
from context_budget import Budget, Checkpoint


class ContextTests(unittest.TestCase):
    def test_budget_levels(self):
        b = Budget(32_000, 4_000, 2_000)
        self.assertEqual(b.active_input_limit, 26_000)
        self.assertEqual(b.decide(10_000), "continue")
        self.assertEqual(b.decide(21_000), "checkpoint")
        self.assertEqual(b.decide(26_000), "block")
        self.assertEqual(b.decide(29_000), "block")

    def test_threshold_is_project_choice(self):
        conservative = Budget(32_000, 4_000, 2_000, 0.6)
        normal = Budget(32_000, 4_000, 2_000, 0.8)
        self.assertEqual(conservative.decide(18_000), "checkpoint")
        self.assertEqual(normal.decide(18_000), "continue")

    def test_invalid_inputs(self):
        for args in [(10, 10, 0), (100, -2, 2)]:
            with self.assertRaises(ValueError):
                Budget(*args)
        with self.assertRaises(ValueError):
            Budget(32_000, 4_000, 2_000).decide(-1)
        with self.assertRaises(ValueError):
            Budget(32_000, 4_000, 2_000).decide(True)

    def test_checkpoint_preserves_unfinished_and_constraints(self):
        cp = Checkpoint(
            goal="Fix failing parser test",
            constraints=("Do not modify production data",),
            verified=("Failure reproduced in test_parser.py",),
            unfinished=("Apply minimal fix", "Run focused tests"),
            references=("src/parser.py", "tests/test_parser.py"),
            open_questions=("Is Unicode input expected?",),
        )
        d = cp.as_dict()
        self.assertEqual(len(d["unfinished"]), 2)
        self.assertTrue(d["constraints"])
        with self.assertRaises(ValueError):
            Checkpoint("Task", (), (), (), (), ())


if __name__ == "__main__":
    unittest.main()
