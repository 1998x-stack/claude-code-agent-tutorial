import unittest
from types import SimpleNamespace as NS
from agent_engine import run_events


class Block:
    def __init__(self, kind, **parts):
        self.type = kind
        self.__dict__.update(parts)

    def model_dump(self, **kwargs):
        return dict(self.__dict__)


class Client:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.histories = []
        self.messages = NS(create=self.create)

    def create(self, **kw):
        self.histories.append([
            {"role": m["role"], "content": m["content"]}
            for m in kw["messages"]
        ])
        return next(self.replies)


def valid(name, arg):
    return str(arg["a"] + arg["b"]), False


class EngineTests(unittest.TestCase):
    def test_feedback_order_and_final(self):
        cli = Client([
            NS(stop_reason="tool_use", content=[
                Block("text", text="calculating"),
                Block("tool_use", id="t1", name="add_numbers", input={"a": 2, "b": 3}),
                Block("tool_use", id="t2", name="add_numbers", input={"a": 4, "b": 5}),
            ]),
            NS(stop_reason="end_turn", content=[Block("text", text="5 and 9")])
        ])
        events = list(run_events(cli, "fake", "sum", valid))
        self.assertEqual([x.kind for x in events], ["request", "tool_result", "tool_result", "request", "final"])
        self.assertEqual([m["role"] for m in cli.histories[1]], ["user", "assistant", "user"])
        self.assertEqual([t["tool_use_id"] for t in cli.histories[1][-1]["content"]], ["t1", "t2"])
        self.assertEqual(events[-1].detail, "5 and 9")

    def test_partial_response_never_reports_success(self):
        cli = Client([NS(stop_reason="max_tokens", content=[Block("text", text="incomplete")])])
        events = list(run_events(cli, "fake", "task", valid))
        self.assertEqual(events[-1].kind, "halt")
        self.assertIn("max_tokens", events[-1].detail)

    def test_tool_failure_still_has_result(self):
        cli = Client([
            NS(stop_reason="tool_use", content=[
                Block("tool_use", id="err", name="bad", input={})
            ])
        ])
        def fail(*_): raise ValueError("wrong")
        events = list(run_events(cli, "fake", "task", fail, max_turns=1))
        self.assertEqual([e.kind for e in events], ["request", "tool_result", "halt"])
        self.assertIn("error", events[1].detail)

    def test_cancel_avoids_model_call(self):
        cli = Client([])
        events = list(run_events(cli, "fake", "task", valid, cancelled=lambda: True))
        self.assertEqual(events[0].detail, "cancelled")
        self.assertFalse(cli.histories)


if __name__ == "__main__":
    unittest.main()
