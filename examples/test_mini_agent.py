"""Deterministic offline tests: no SDK, API Key or network needed."""
import unittest
from types import SimpleNamespace as NS
from mini_agent import dispatch_tool, run_agent


class Block:
    def __init__(self, type, **kwargs):
        self.type = type
        self.__dict__.update(kwargs)

    def model_dump(self, **_):
        return dict(self.__dict__)


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.messages = NS(create=self.create)

    def create(self, **kwargs):
        self.calls.append({**kwargs, 'messages': [m.copy() for m in kwargs['messages']]})
        return next(self.responses)


class AgentTests(unittest.TestCase):
    def test_tool_validation(self):
        self.assertEqual(dispatch_tool("add_numbers", {"a": 5, "b": 7}), ("12", False))
        self.assertTrue(dispatch_tool("bash", {"command": "ls"})[1])
        self.assertTrue(dispatch_tool("add_numbers", {"a": True, "b": 2})[1])
        self.assertTrue(dispatch_tool("add_numbers", {"a": 10**9, "b": 1})[1])

    def test_correct_history_order_and_two_parallel_tools(self):
        responses = [
            NS(stop_reason="tool_use", content=[
                Block("text", text="Let me calculate both."),
                Block("tool_use", id="id1", name="add_numbers", input={"a": 1, "b": 2}),
                Block("tool_use", id="id2", name="add_numbers", input={"a": 3, "b": 4}),
            ]),
            NS(stop_reason="end_turn", content=[Block("text", text="3 and 7")]),
        ]
        cli = FakeClient(responses)
        self.assertEqual(run_agent(cli, "test-model", "two sums"), "3 and 7")
        history = cli.calls[1]["messages"]
        self.assertEqual([m["role"] for m in history], ["user", "assistant", "user"])
        self.assertEqual(len(history[1]["content"]), 3)
        self.assertEqual(len(history[2]["content"]), 2)
        self.assertEqual([x["tool_use_id"] for x in history[2]["content"]], ["id1", "id2"])
        self.assertEqual([x["content"] for x in history[2]["content"]], ["3", "7"])

    def test_nonfinal_max_tokens(self):
        client = FakeClient([NS(stop_reason="max_tokens", content=[Block("text", text="partial")])])
        with self.assertRaisesRegex(RuntimeError, "max_tokens"):
            run_agent(client, "test-model", "hello")

    def test_step_budget(self):
        client = FakeClient([NS(stop_reason="tool_use", content=[
            Block("tool_use", id="c1", name="add_numbers", input={"a": 1, "b": 2})])])
        with self.assertRaisesRegex(RuntimeError, "maximum"):
            run_agent(client, "test-model", "hello", max_turns=1)


if __name__ == "__main__":
    unittest.main()
