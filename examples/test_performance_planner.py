import unittest
from performance_planner import (
    WorkItem, ModelCandidate, schedule, makespan, select_model
)


class PerformancePlannerTests(unittest.TestCase):
    def test_independent_work_can_overlap(self):
        items = (WorkItem("a", 1000), WorkItem("b", 800))
        serial = schedule(items, 1)
        parallel = schedule(items, 2)
        self.assertEqual(makespan(serial), 1800)
        self.assertEqual(makespan(parallel), 1000)
        self.assertEqual(parallel[0].start_ms, parallel[1].start_ms)

    def test_dependencies_are_never_violated(self):
        items = (
            WorkItem("read_a", 800),
            WorkItem("read_b", 600),
            WorkItem("analyze", 400, ("read_a", "read_b")),
            WorkItem("write", 200, ("analyze",)),
        )
        plan = {x.name: x for x in schedule(items, 2)}
        self.assertGreaterEqual(plan["analyze"].start_ms, plan["read_a"].end_ms)
        self.assertGreaterEqual(plan["analyze"].start_ms, plan["read_b"].end_ms)
        self.assertGreaterEqual(plan["write"].start_ms, plan["analyze"].end_ms)

    def test_missing_dependency_cycle_and_duplicate_fail(self):
        for items in (
            (WorkItem("a", 1, ("missing",)),),
            (WorkItem("a", 1, ("b",)), WorkItem("b", 1, ("a",))),
            (WorkItem("a", 1), WorkItem("a", 2)),
        ):
            with self.subTest(items=items), self.assertRaises(ValueError):
                schedule(items, 2)

    def test_model_router_uses_measured_constraints(self):
        choices = (
            ModelCandidate("small", .91, 900, 1.0),
            ModelCandidate("large", .98, 1400, 4.0),
            ModelCandidate("fast-but-weak", .75, 300, .3),
        )
        chosen = select_model(choices, min_quality=.90, max_p95_latency_ms=1000)
        self.assertEqual(chosen.model_id, "small")
        with self.assertRaises(LookupError):
            select_model(choices, min_quality=.99)

    def test_invalid_measurements_and_worker_count(self):
        with self.assertRaises(ValueError):
            schedule((WorkItem("a", 1),), 0)
        with self.assertRaises(ValueError):
            select_model((ModelCandidate("x", 1.1, 10, 1),), min_quality=.8)


if __name__ == "__main__":
    unittest.main()
