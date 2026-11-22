import unittest
from datetime import date, timedelta
from ecosystem_review import ResourceEvidence


class EcosystemReviewTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 22)
        self.good = ResourceEvidence(
            name="example", url="https://github.com/example/repo",
            checked_on=self.today, archived=False, license_id="MIT",
            version_or_commit_pinned=True, permissions_reviewed=True,
            network_behavior_reviewed=True, data_handling_reviewed=True,
            dependencies_reviewed=True,
        )

    def test_complete_evidence_has_no_gaps(self):
        self.assertEqual(self.good.gaps(today=self.today), ())

    def test_each_missing_control_is_visible(self):
        weak = ResourceEvidence(
            name="plugin", url="https://github.com/example/plugin",
            checked_on=self.today, archived=False, license_id=None,
            version_or_commit_pinned=False, permissions_reviewed=False,
            network_behavior_reviewed=False, data_handling_reviewed=False,
            dependencies_reviewed=False,
        )
        gaps = weak.gaps(today=self.today)
        self.assertEqual(len(gaps), 6)
        self.assertTrue(any("license" in x for x in gaps))
        self.assertTrue(any("permissions" in x for x in gaps))

    def test_stale_and_archived_resources_are_flagged(self):
        old = ResourceEvidence(
            name="old", url="https://github.com/example/old",
            checked_on=self.today - timedelta(days=120), archived=True,
            license_id="MIT", version_or_commit_pinned=True,
            permissions_reviewed=True, network_behavior_reviewed=True,
            data_handling_reviewed=True, dependencies_reviewed=True,
        )
        gaps = old.gaps(today=self.today, max_age_days=90)
        self.assertTrue(any("archived" in x for x in gaps))
        self.assertTrue(any("stale" in x for x in gaps))

    def test_invalid_url_and_future_date_rejected(self):
        bad = ResourceEvidence(
            name="bad", url="http://example.com", checked_on=self.today,
            archived=False, license_id="MIT", version_or_commit_pinned=True,
            permissions_reviewed=True, network_behavior_reviewed=True,
            data_handling_reviewed=True, dependencies_reviewed=True,
        )
        with self.assertRaises(ValueError):
            bad.gaps(today=self.today)
        future = ResourceEvidence(
            name="future", url="https://example.com",
            checked_on=self.today + timedelta(days=1), archived=False,
            license_id="MIT", version_or_commit_pinned=True,
            permissions_reviewed=True, network_behavior_reviewed=True,
            data_handling_reviewed=True, dependencies_reviewed=True,
        )
        with self.assertRaises(ValueError):
            future.gaps(today=self.today)


if __name__ == "__main__":
    unittest.main()
