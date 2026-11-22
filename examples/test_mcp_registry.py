import unittest
from mcp_registry import ToolRegistry


def page(name="search", annotations=None):
    return {"resultType": "complete", "tools": [{
        "name": name,
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        "annotations": annotations or {"readOnlyHint": True},
    }]}


class MCPRegistryTests(unittest.TestCase):
    def test_tool_names_are_server_scoped(self):
        reg = ToolRegistry()
        reg.add_server_tools("alpha", (page(),))
        reg.add_server_tools("beta", (page(),))
        self.assertEqual(reg.names(), ("alpha::search", "beta::search"))

    def test_permission_is_not_annotation(self):
        reg = ToolRegistry()
        reg.add_server_tools("remote", (page(
            annotations={"readOnlyHint": True, "destructiveHint": False}),))
        with self.assertRaises(PermissionError):
            reg.prepare_call("remote::search", {"query": "hi"}, 4, frozenset())
        msg = reg.prepare_call("remote::search", {"query": "hi"}, 4,
                               frozenset({"remote::search"}))
        self.assertEqual(msg["params"]["name"], "search")
        self.assertEqual(msg["params"]["_meta"][
            "io.modelcontextprotocol/protocolVersion"], "2026-07-28")

    def test_requires_args_exactly_and_checks_type(self):
        reg = ToolRegistry()
        reg.add_server_tools("docs", (page(),))
        allow = frozenset({"docs::search"})
        for args in ({}, {"query": 123}, {"query": "hi", "extra": "x"}):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    reg.prepare_call("docs::search", args, 2, allow)

    def test_unknown_and_duplicate_tools_fail(self):
        reg = ToolRegistry()
        with self.assertRaises(ValueError):
            reg.add_server_tools("a", (page(), page()))
        reg.add_server_tools("a", (page(),))
        with self.assertRaises(ValueError):
            reg.add_server_tools("a", (page("find"),))
        with self.assertRaises(PermissionError):
            reg.prepare_call("missing::search", {}, 4,
                             frozenset({"missing::search"}))


if __name__ == "__main__":
    unittest.main()
