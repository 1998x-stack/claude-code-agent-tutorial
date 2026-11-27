import json
import unittest
from agent_observability import TraceRecorder


class TraceRecorderTests(unittest.TestCase):
    def setUp(self):
        self.t = TraceRecorder()

    def test_correlates_api_tool_result_and_permission_decision(self):
        self.t.record(trace_id="t1", span_id="r1", name="api.request",
                      timestamp_ms=1, attributes={
                          "request_id":"req-1", "model":"sonnet",
                          "input_tokens":100, "cache_read_tokens":30,
                          "cache_creation_tokens":10, "output_tokens":20,
                          "duration_ms":800, "success":True})
        self.t.record(trace_id="t1", span_id="d1", parent_span_id="r1",
                      name="tool.decision", timestamp_ms=2, attributes={
                          "tool_use_id":"call-1", "tool_name":"Write",
                          "decision":"accept", "decision_source":"user"})
        self.t.record(trace_id="t1", span_id="x1", parent_span_id="r1",
                      name="tool.result", timestamp_ms=3, attributes={
                          "tool_use_id":"call-1", "request_id":"req-1",
                          "tool_name":"Write", "success":True,
                          "duration_ms":15, "input_bytes":30, "result_bytes":10})
        summary = self.t.summary()
        self.assertEqual(summary["input_total_including_cache"], 140)
        self.assertEqual(summary["token_counts"]["output"], 20)
        self.assertEqual(summary["tools"]["completed"], 1)
        self.assertEqual(summary["tools"]["rejected"], 0)

    def test_rejected_tool_has_decision_but_no_tool_result(self):
        self.t.record(trace_id="t", span_id="d", name="tool.decision",
                      timestamp_ms=1, attributes={
                          "tool_use_id":"c1", "tool_name":"Bash", "decision":"reject"})
        self.assertEqual(self.t.summary()["tools"]["rejected"], 1)
        self.assertEqual(self.t.summary()["tools"]["completed"], 0)

    def test_allowlist_drops_sensitive_fields(self):
        self.t.record(trace_id="t", span_id="r", name="api.request",
                      timestamp_ms=1, attributes={
                          "model":"sonnet", "input_tokens":1, "output_tokens":2,
                          "prompt":"user secret and source code",
                          "messages":[{"role":"user","content":"sensitive"}]})
        encoded = self.t.to_jsonl()
        self.assertNotIn("prompt", encoded)
        self.assertNotIn("source code", encoded)
        self.assertNotIn("sensitive", encoded)

    def test_invalid_values_and_duplicate_span_fail(self):
        with self.assertRaises(ValueError):
            self.t.record(trace_id="t", span_id="r", name="api.request",
                          timestamp_ms=1, attributes={
                              "model":"x", "input_tokens":-1, "output_tokens":0})
        attrs = {"model":"x", "input_tokens":1, "output_tokens":1}
        self.t.record(trace_id="t", span_id="r", name="api.request",
                      timestamp_ms=1, attributes=attrs)
        with self.assertRaises(ValueError):
            self.t.record(trace_id="t", span_id="r", name="api.request",
                          timestamp_ms=2, attributes=attrs)

    def test_compaction_invariant_and_jsonl(self):
        with self.assertRaises(ValueError):
            self.t.record(trace_id="t", span_id="c", name="session.compaction",
                          timestamp_ms=1, attributes={"before_tokens":10,"after_tokens":11})
        self.t.record(trace_id="t", span_id="c", name="session.compaction",
                      timestamp_ms=1, attributes={"before_tokens":100,"after_tokens":40})
        self.assertEqual(json.loads(self.t.to_jsonl())["name"], "session.compaction")


if __name__ == "__main__":
    unittest.main()
