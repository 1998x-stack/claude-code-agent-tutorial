import unittest
from context_tuning import InputBreakdown, Usage, simulate, retain_critical


class TuningTests(unittest.TestCase):
    def setUp(self):
        self.b = InputBreakdown(3000, 5000, 8000, 6000)

    def test_different_techniques_change_different_counters(self):
        v = simulate(self.b, deferred_schema_tokens=3000,
                     removed_stale_result_tokens=4000,
                     cached_prefix_tokens=4500)
        self.assertEqual(v["baseline_input_tokens"], 22000)
        self.assertEqual(v["optimized_input_tokens"], 15000)
        self.assertEqual(v["saved_context_tokens"], 7000)
        self.assertEqual(v["cached_context_savings"], 0)

    def test_caching_alone_does_not_reduce_context(self):
        v = simulate(self.b, cached_prefix_tokens=10000)
        self.assertEqual(v["optimized_input_tokens"], self.b.total())
        self.assertEqual(v["saved_context_tokens"], 0)

    def test_api_usage_counters_are_additive(self):
        u = Usage(input_tokens=2000, cache_creation_input_tokens=3000,
                  cache_read_input_tokens=5000, output_tokens=1000)
        self.assertEqual(u.full_input(), 10000)
        self.assertEqual(u.cache_read_fraction(), 0.5)

    def test_reject_invalid_and_out_of_range(self):
        for kw in ({"deferred_schema_tokens":6000},
                   {"removed_stale_result_tokens":-1},
                   {"cached_prefix_tokens":999999}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                simulate(self.b, **kw)
        with self.assertRaises(ValueError):
            InputBreakdown(True, 1, 2, 3).total()

    def test_protected_facts_cannot_be_silently_lost(self):
        required = {"no production writes", "run tests"}
        retain_critical({"no production writes", "run tests", "source path"}, required)
        with self.assertRaises(ValueError):
            retain_critical({"run tests"}, required)


if __name__ == "__main__":
    unittest.main()
