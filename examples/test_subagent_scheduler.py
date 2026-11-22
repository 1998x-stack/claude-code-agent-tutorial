import unittest
from delegation_contract import delegate, Finding
from subagent_scheduler import run_batch


def job(name):
    return delegate(name=name, goal=f"Review {name}",
                    refs=(f"{name}.py",),
                    parent_allowed=frozenset({"Read"}),
                    requested_tools=frozenset({"Read"}), budget=3)


class SchedulerTests(unittest.TestCase):
    def test_input_order_and_finding_validation(self):
        jobs = (job("alpha"), job("beta"))
        result = run_batch(jobs, lambda j: Finding(
            j.name, f"Checked {j.name}", j.evidence_refs, ()
        ), max_workers=2)
        self.assertEqual([r.agent for r in result], ["alpha", "beta"])
        self.assertEqual([r.status for r in result], ["ok", "ok"])

    def test_raises_inside_worker_becomes_error(self):
        def worker(j):
            if j.name == "beta":
                raise RuntimeError("failed")
            return Finding(j.name, "OK", j.evidence_refs, ())
        result = run_batch((job("alpha"), job("beta")), worker)
        self.assertEqual(result[0].status, "ok")
        self.assertEqual(result[1].status, "error")
        self.assertEqual(result[1].reason, "RuntimeError")

    def test_undeclared_evidence_fails(self):
        result = run_batch((job("alpha"),),
            lambda j: Finding(j.name, "OK", ("secrets.env",), ()))
        self.assertEqual(result[0].status, "error")

    def test_batch_limit_and_name_collision(self):
        with self.assertRaises(ValueError):
            run_batch((job("alpha"), job("alpha")), lambda j: None)
        with self.assertRaises(ValueError):
            run_batch((job("alpha"),), lambda j: None, max_workers=99)
        with self.assertRaises(ValueError):
            run_batch((), lambda j: None)


if __name__ == "__main__":
    unittest.main()
