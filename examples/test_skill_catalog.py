import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from skill_catalog import SkillCatalog


class SkillCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        d = self.root / "review"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: review\ndescription: Review Python code\nallowed-tools: Bash\n---\n"
            "Inspect code and cite file locations.", encoding="utf-8"
        )
        self.catalog = SkillCatalog(self.root)

    def test_description_discovery_then_explicit_load(self):
        self.assertEqual(self.catalog.descriptions(),
                         (("review", "Review Python code"),))
        skill = self.catalog.load("review")
        self.assertIn("cite file locations", skill.instructions)
        self.assertNotIn("Bash", skill.instructions)

    def test_rejects_traversal_and_symlink(self):
        for s in ("../review", "/review", "review/../../"):
            with self.assertRaises(ValueError):
                self.catalog.load(s)
        (self.root / "linked").symlink_to(self.root / "review", target_is_directory=True)
        with self.assertRaises(ValueError):
            self.catalog.load("linked")

    def test_missing_and_malformed_skill(self):
        with self.assertRaises(ValueError):
            self.catalog.load("missing")
        (self.root / "review" / "SKILL.md").write_text("no header", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.catalog.load("review")


if __name__ == "__main__":
    unittest.main()
