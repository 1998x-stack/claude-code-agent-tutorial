import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from skill_runtime import SkillCatalog


def write_skill(root, name, front, body="Do the task."):
    folder = root / name
    folder.mkdir()
    (folder / "SKILL.md").write_text(
        "---\n" + front + "\n---\n" + body, encoding="utf-8"
    )
    return folder


class SkillRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_metadata_discovery_and_lazy_body_load(self):
        write_skill(self.root, "review", "name: review\ndescription: Review source code")
        catalog = SkillCatalog(self.root)
        found = catalog.discover()
        self.assertEqual(found[0].description, "Review source code")
        self.assertFalse(hasattr(found[0], "body"))
        self.assertIn("Do the task", catalog.invoke("review", "model").body)

    def test_invocation_controls_are_not_interchangeable(self):
        write_skill(self.root, "deploy",
                    "name: deploy\ndescription: Deploy on request\n"
                    "disable-model-invocation: true")
        catalog = SkillCatalog(self.root)
        self.assertTrue(catalog.can_invoke("deploy", "user"))
        self.assertFalse(catalog.can_invoke("deploy", "model"))
        with self.assertRaises(PermissionError):
            catalog.invoke("deploy", "model")
        write_skill(self.root, "background",
                    "name: background\ndescription: Background knowledge\n"
                    "user-invocable: false")
        self.assertFalse(catalog.can_invoke("background", "user"))
        self.assertTrue(catalog.can_invoke("background", "model"))

    def test_fork_and_turn_scoped_tool_declaration_are_metadata_only(self):
        write_skill(self.root, "audit",
                    "name: audit\ndescription: Audit a change\ncontext: fork\n"
                    "agent: Explore\nbackground: false\n"
                    "allowed-tools:\n  - Read\n  - Grep\n"
                    "paths:\n  - src/**/*.py",
                    "Read files and report findings.")
        doc = SkillCatalog(self.root).invoke("audit", "user")
        self.assertEqual(doc.metadata.context, "fork")
        self.assertEqual(doc.metadata.agent, "Explore")
        self.assertFalse(doc.metadata.background)
        self.assertEqual(doc.metadata.allowed_tools, ("Read", "Grep"))
        self.assertIn("Read files", doc.body)

    def test_bad_frontmatter_is_reported_not_executed(self):
        write_skill(self.root, "broken", "name: wrong\ndescription: Bad")
        catalog = SkillCatalog(self.root)
        self.assertEqual(catalog.discover(), ())
        self.assertTrue(catalog.errors)
        with self.assertRaises(ValueError):
            catalog.invoke("broken", "user")

    def test_duplicate_frontmatter_key_is_rejected(self):
        write_skill(self.root, "duplicate",
                    "name: duplicate\ndescription: First\ndescription: Second")
        catalog = SkillCatalog(self.root)
        self.assertEqual(catalog.discover(), ())
        self.assertIn("duplicate frontmatter key", catalog.errors[0])

    def test_reject_traversal_windows_paths_symlink_and_external_resource(self):
        folder = write_skill(self.root, "safe", "name: safe\ndescription: Safe")
        (folder / "reference.md").write_text("reference", encoding="utf-8")
        catalog = SkillCatalog(self.root)
        self.assertEqual(catalog.read_supporting_file("safe", "reference.md"), "reference")
        for path in ("../outside", "/etc/passwd", "a/../../secret",
                     "C:/Windows/win.ini", r"..\outside", "file.txt:secret", "bad\npath"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                catalog.read_supporting_file("safe", path)
        (self.root / "alias").symlink_to(folder, target_is_directory=True)
        with self.assertRaises(ValueError):
            catalog.invoke("alias", "user")
        (folder / "escape.md").symlink_to(self.root / "outside")
        with self.assertRaises(ValueError):
            catalog.read_supporting_file("safe", "escape.md")

    def test_invalid_caller_and_context_are_rejected(self):
        write_skill(self.root, "forked",
                    "name: forked\ndescription: Fork\ncontext: shared")
        catalog = SkillCatalog(self.root)
        write_skill(self.root, "review", "name: review\ndescription: Review")
        with self.assertRaises(ValueError):
            catalog.invoke("forked", "user")
        with self.assertRaises(ValueError):
            catalog.invoke("review", "system")


if __name__ == "__main__":
    unittest.main()
