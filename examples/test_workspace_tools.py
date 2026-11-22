"""No model, network, shell or privileged filesystem access in these tests."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from workspace_tools import Workspace, ToolError


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.ws = Workspace(self.root)

    def test_explicit_approval_and_atomic_write(self):
        result, error = self.ws.dispatch(
            "Write", {"path": "a.txt", "content": "before"}, approved=False
        )
        self.assertTrue(error)
        self.assertFalse((self.root / "a.txt").exists())
        self.assertFalse(self.ws.dispatch(
            "Write", {"path": "a.txt", "content": "before"}, approved=True
        )[1])
        self.assertEqual((self.root / "a.txt").read_text(), "before")
        self.assertTrue(self.ws.dispatch(
            "Write", {"path": "a.txt", "content": "overwrite"}, approved=True
        )[1])
        self.assertTrue(self.ws.dispatch(
            "Edit", {"path": "a.txt", "old": "before", "new": "after"}
        )[1])
        self.assertFalse(self.ws.dispatch(
            "Edit", {"path": "a.txt", "old": "before", "new": "after"},
            approved=True
        )[1])
        self.assertEqual(self.ws.read("a.txt"), "after")

    def test_rejects_ambiguous_edit(self):
        (self.root / "dupe.txt").write_text("x x", encoding="utf-8")
        self.assertTrue(self.ws.dispatch(
            "Edit", {"path": "dupe.txt", "old": "x", "new": "y"},
            approved=True
        )[1])
        self.assertEqual(self.ws.read("dupe.txt"), "x x")

    def test_blocks_sensitive_and_escape_paths(self):
        for path in ("../escape", "/tmp/external", ".git/config", ".env", ".env.local"):
            with self.subTest(path=path):
                with self.assertRaises(ToolError):
                    self.ws.target(path)
        self.assertTrue(self.ws.dispatch("Read", {"path": "../outside"})[1])
        (self.root / "link").symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(ToolError):
            self.ws.target("link/escape")

    def test_no_shell_execution(self):
        self.assertEqual(self.ws.bash_preview("ls"), "")
        self.assertEqual(self.ws.bash_preview("pwd"), str(self.root))
        for command in ("ls -la", "echo hi", "pwd; rm -rf .", "cat .env"):
            with self.assertRaises(ToolError):
                self.ws.bash_preview(command)

    def test_rejects_unknown_and_extra_arguments(self):
        self.assertTrue(self.ws.dispatch("Shell", {"command": "ls"})[1])
        self.assertTrue(self.ws.dispatch("Read", {"path": "a", "ignored": "x"})[1])
        self.assertTrue(self.ws.dispatch("Write", "not-a-dict", approved=True)[1])


if __name__ == "__main__":
    unittest.main()
