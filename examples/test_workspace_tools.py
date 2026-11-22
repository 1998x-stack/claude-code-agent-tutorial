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

    def test_blocks_sensitive_escape_windows_and_control_paths(self):
        for path in ("../escape", "/tmp/external", ".git/config", ".env", ".env.local",
                     ".GIT/config", ".ENV", ".SSH/id_rsa", "C:/Windows/win.ini",
                     "C:relative.txt", "file.txt:secret", "bad\nname.txt"):
            with self.subTest(path=path), self.assertRaises(ToolError):
                self.ws.target(path)
        self.assertTrue(self.ws.dispatch("Read", {"path": "../outside"})[1])
        (self.root / "link").symlink_to(self.root.parent, target_is_directory=True)
        with self.assertRaises(ToolError):
            self.ws.target("link/escape")

    def test_read_limit_counts_utf8_bytes_and_bounds_actual_read(self):
        (self.root / "unicode.txt").write_text("界" * 6000, encoding="utf-8")
        with self.assertRaises(ToolError):
            self.ws.read("unicode.txt")
        (self.root / "ok.txt").write_text("界" * 100, encoding="utf-8")
        self.assertEqual(len(self.ws.read("ok.txt")), 100)

    def test_no_shell_execution_and_sensitive_listing(self):
        (self.root / ".ENV").write_text("secret", encoding="utf-8")
        self.assertEqual(self.ws.bash_preview("pwd"), str(self.root))
        self.assertNotIn(".ENV", self.ws.bash_preview("ls"))
        for command in ("ls -la", "echo hi", "pwd; rm -rf .", "cat .env"):
            with self.assertRaises(ToolError):
                self.ws.bash_preview(command)

    def test_rejects_unknown_and_extra_arguments(self):
        self.assertTrue(self.ws.dispatch("Shell", {"command": "ls"})[1])
        self.assertTrue(self.ws.dispatch([], {"command": "ls"})[1])
        self.assertTrue(self.ws.dispatch("Read", {"path": "a", "ignored": "x"})[1])
        self.assertTrue(self.ws.dispatch("Write", "not-a-dict", approved=True)[1])


if __name__ == "__main__":
    unittest.main()
