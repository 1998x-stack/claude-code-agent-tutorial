import unittest
import json
from mcp_protocol import request, legacy_initialize, parse_response, stdio_line


class MCPProtocolTests(unittest.TestCase):
    def test_modern_tool_list_carries_per_request_metadata(self):
        req = request("tools/list", 7, {})
        meta = req["params"]["_meta"]
        self.assertEqual(meta["io.modelcontextprotocol/protocolVersion"], "2026-07-28")
        self.assertIn("io.modelcontextprotocol/clientCapabilities", meta)
        self.assertEqual(req["id"], 7)

    def test_legacy_has_initialize_and_no_modern_meta(self):
        old = legacy_initialize()
        self.assertEqual(old["method"], "initialize")
        self.assertEqual(old["params"]["protocolVersion"], "2025-11-25")
        self.assertNotIn("_meta", old["params"])
        with self.assertRaises(ValueError):
            request("initialize", 1)

    def test_correlate_id_and_result_type(self):
        msg = {"jsonrpc":"2.0","id":3,"result":{
            "resultType":"complete","tools":[]}}
        self.assertEqual(parse_response(msg, 3)["tools"], [])
        with self.assertRaises(ValueError):
            parse_response(msg, 4)
        with self.assertRaises(ValueError):
            parse_response({"jsonrpc":"2.0","id":3,"result":{"tools":[]}}, 3)

    def test_input_required_is_not_completion(self):
        msg = {"jsonrpc":"2.0","id":11,"result":{
            "resultType":"input_required","inputRequests":{}}}
        self.assertEqual(parse_response(msg, 11)["resultType"], "input_required")

    def test_error_and_injection_boundaries(self):
        with self.assertRaises(ValueError):
            request("tools/list", 3, {"_meta": {"fake": "yes"}})
        with self.assertRaisesRegex(ValueError, "JSON-RPC error"):
            parse_response({"jsonrpc":"2.0","id":5,"error":{
                "code":-32022,"message":"Unsupported protocol version"}}, 5)
        line = stdio_line(request("tools/call", 2, {
            "name": "echo", "arguments": {"text": "hello\\nworld"}}))
        self.assertEqual(json.loads(line)["id"], 2)
        self.assertEqual(line.count("\n"), 1)


if __name__ == "__main__":
    unittest.main()
