import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from safe_coding_agent import (
    SafeCodingAgent, DemoClient, DemoBlock, DemoReply, offline_demo,
)
from workspace_tools import Workspace

class SequenceMessages:
    def __init__(self, replies):
        self._replies = iter(replies)
        self.calls = []
    def create(self, **kwargs):
        self.calls.append(kwargs)
        return next(self._replies)

class SequenceClient:
    def __init__(self, replies):
        self.messages = SequenceMessages(replies)

class CodingAgentIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "hello.txt").write_text("hello\n", encoding="utf-8")
        self.ws = Workspace(self.root)

    def make(self, replies):
        client = SequenceClient(replies)
        return SafeCodingAgent(client, self.ws, "test-model"), client

    def test_end_to_end_offline_demo_does_not_write(self):
        run = offline_demo()
        self.assertEqual(run.stop_reason, "model_ended_not_verified")
        self.assertEqual(run.turns, 3)
        self.assertFalse(any(x.failed for x in run.outcomes))
        self.assertIn("NOT APPLIED", run.outcomes[-1].result)
        self.assertEqual(len(run.history), 6)

    def test_tool_results_have_matching_ids_in_single_message(self):
        agent, client = self.make([
            DemoReply("tool_use", [
                DemoBlock("tool_use", id="id1", name="ReadFile", input={"path":"hello.txt"}),
                DemoBlock("tool_use", id="id2", name="ProposeEdit",
                          input={"path":"hello.txt","old":"hello","new":"hello world"}),
            ]),
            DemoReply("end_turn", [DemoBlock("text", text="proposal")]),
        ])
        result = agent.run("inspect and propose")
        self.assertEqual([x.tool_use_id for x in result.outcomes], ["id1","id2"])
        responses = result.history[2]["content"]
        self.assertEqual([x["tool_use_id"] for x in responses], ["id1","id2"])
        self.assertTrue(all(x["is_error"] is False for x in responses))
        self.assertEqual(self.ws.read("hello.txt"), "hello\n")

    def test_unsafe_names_and_paths_result_in_errors(self):
        agent, client = self.make([
            DemoReply("tool_use", [
                DemoBlock("tool_use", id="x", name="Bash", input={"command":"rm -rf ."}),
                DemoBlock("tool_use", id="y", name="ReadFile", input={"path":"../.env"}),
            ]),
            DemoReply("end_turn", [DemoBlock("text", text="cannot access")]),
        ])
        run = agent.run("test")
        self.assertTrue(all(x.failed for x in run.outcomes))
        self.assertEqual(run.stop_reason, "model_ended_not_verified")

    def test_duplicate_tool_id_halts_before_execution(self):
        agent, client = self.make([
            DemoReply("tool_use", [
                DemoBlock("tool_use", id="dup", name="ReadFile", input={"path":"hello.txt"}),
                DemoBlock("tool_use", id="dup", name="ReadFile", input={"path":"hello.txt"}),
            ]),
        ])
        run = agent.run("inspect")
        self.assertEqual(run.stop_reason, "duplicate_tool_id")
        self.assertEqual(run.outcomes, ())

    def test_budget_and_max_tokens_are_not_complete(self):
        agent, client = self.make([DemoReply("max_tokens", [DemoBlock("text", text="...")])])
        self.assertEqual(agent.run("inspect").stop_reason, "halt:max_tokens")
        agent2, _ = self.make([DemoReply("tool_use", [
            DemoBlock("tool_use", id="id1", name="ReadFile", input={"path":"hello.txt"}),
        ])])
        agent2.max_turns = 1
        self.assertEqual(agent2.run("inspect").stop_reason, "turn_budget_exhausted")

    def test_exact_tool_arguments_and_unique_edit_match(self):
        agent, _ = self.make([])
        self.assertTrue(agent.execute("ReadFile", {"path":"hello.txt","extra":1})[1])
        self.assertTrue(agent.execute("ProposeEdit", {"path":"hello.txt","old":"not here","new":"y"})[1])
        diff, failed = agent.execute("ProposeEdit", {"path":"hello.txt","old":"hello","new":"good day"})
        self.assertFalse(failed)
        self.assertIn("+good day", diff)
        self.assertEqual(self.ws.read("hello.txt"), "hello\n")

if __name__ == "__main__":
    unittest.main()
