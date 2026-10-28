"""Task 4 tests: the inspection core, driven by saved Docker output."""

import os
import unittest
from datetime import datetime, timedelta, timezone

import docker_janitor as dj

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
LOCAL = timezone(timedelta(hours=3, minutes=30))
NOW = datetime(2026, 10, 22, 21, 40, tzinfo=LOCAL)


def fixture(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as handle:
        return handle.read()


class ParseSizeTests(unittest.TestCase):
    def test_units(self):
        self.assertEqual(dj.parse_size("0B"), 0)
        self.assertEqual(dj.parse_size("98.3kB"), 98300)
        self.assertEqual(dj.parse_size("1.5MB"), 1500000)
        self.assertEqual(dj.parse_size("20.83GB"), 20830000000)

    def test_unknown_size_is_zero(self):
        self.assertEqual(dj.parse_size("N/A"), 0)
        self.assertEqual(dj.parse_size(""), 0)


class ParseSystemDfTests(unittest.TestCase):
    def test_reported_reclaimable_matches_docker(self):
        parsed = dj.parse_system_df(fixture("system_df.txt"))
        self.assertEqual(parsed["images"]["reclaimable"], 23600000000)
        self.assertEqual(parsed["containers"]["reclaimable"], 98300)
        self.assertEqual(parsed["volumes"]["reclaimable"], 48020000)
        self.assertEqual(parsed["cache"]["reclaimable"], 20830000000)

    def test_totals_are_parsed(self):
        parsed = dj.parse_system_df(fixture("system_df.txt"))
        self.assertEqual(parsed["images"]["total"], 63)
        self.assertEqual(parsed["containers"]["total"], 12)
        self.assertEqual(parsed["cache"]["total"], 673)


class UnusedImageTests(unittest.TestCase):
    def setUp(self):
        self.images = dj.parse_images(fixture("images.jsonl"))
        self.used = dj.parse_used_ids(fixture("used_image_ids.txt"))
        self.unique = dj.parse_unique_sizes(fixture("system_df_verbose.txt"))

    def test_fixture_has_the_images_docker_reported(self):
        self.assertEqual(len(self.images), 58)
        self.assertEqual(len(self.used), 12)

    def test_only_old_unused_images_are_selected(self):
        picked = dj.unused_images(self.images, self.used, NOW, 30)
        self.assertEqual(len(picked), 19)
        total = sum(self.unique[image.id] for image in picked)
        self.assertEqual(total, 3558350010)

    def test_higher_threshold_excludes_younger_images(self):
        picked = dj.unused_images(self.images, self.used, NOW, 90)
        self.assertEqual([image.id for image in picked], ["5f5c8640aae0"])

    def test_images_used_by_containers_are_never_selected(self):
        picked = dj.unused_images(self.images, self.used, NOW, 0)
        self.assertFalse({image.id for image in picked} & self.used)

    def test_image_referenced_by_repository_name_is_not_selected(self):
        images = [
            dj.ImageRow(
                id="aabbccddeeff",
                repository="my-app",
                tag="latest",
                created=NOW - timedelta(days=60),
            )
        ]
        used_ids = dj.parse_used_ids("sha256:112233445566|||my-app")
        picked = dj.unused_images(images, used_ids, NOW, 30)
        self.assertEqual(picked, [])

    def test_dangling_images_are_counted_separately(self):
        self.assertEqual(dj.dangling_images(self.images), [])

    def test_eligible_ids_filter_restricts_images_with_old_creation(self):
        images = [
            dj.ImageRow(
                id="e5d8f06a60f2",
                repository="dunglas/mercure",
                tag="latest",
                created=NOW - timedelta(days=35),
            ),
            dj.ImageRow(
                id="aabbccddeeff",
                repository="old-app",
                tag="latest",
                created=NOW - timedelta(days=40),
            ),
        ]
        # Only aabbccddeeff matches the prune until filter
        eligible_ids = {"aabbccddeeff"}
        picked = dj.unused_images(images, set(), NOW, 30, eligible_ids=eligible_ids)
        self.assertEqual([img.id for img in picked], ["aabbccddeeff"])

    def test_empty_eligible_ids_selects_no_images(self):
        images = [
            dj.ImageRow(
                id="e5d8f06a60f2",
                repository="dunglas/mercure",
                tag="latest",
                created=NOW - timedelta(days=35),
            )
        ]
        picked = dj.unused_images(images, set(), NOW, 30, eligible_ids=set())
        self.assertEqual(picked, [])


class ImageFilterHelperTests(unittest.TestCase):
    def test_parse_image_ids(self):
        raw = "e5d8f06a60f2\n  1f028471f346 \n\n"
        self.assertEqual(dj.parse_image_ids(raw), {"e5d8f06a60f2", "1f028471f346"})
        self.assertEqual(dj.parse_image_ids(""), set())
        self.assertEqual(dj.parse_image_ids(None), set())

    def test_matches_eligible_ids(self):
        # exact match
        self.assertTrue(dj._matches_eligible_ids("e5d8f06a60f2", {"e5d8f06a60f2"}))
        # prefix match with sha256 prefix
        full_hash = "sha256:e5d8f06a60f2feb5e91f7ba2046d9184f6339b3498b5d2f5adaeb5bcb080bfc7"
        self.assertTrue(dj._matches_eligible_ids(full_hash, {"e5d8f06a60f2"}))
        self.assertTrue(dj._matches_eligible_ids("e5d8f06a60f2", {full_hash}))
        # not in set
        self.assertFalse(dj._matches_eligible_ids("112233445566", {"e5d8f06a60f2"}))
        # empty set
        self.assertFalse(dj._matches_eligible_ids("e5d8f06a60f2", set()))
        # None is fallback (accepts)
        self.assertTrue(dj._matches_eligible_ids("e5d8f06a60f2", None))


class CacheRecordTests(unittest.TestCase):
    def test_private_old_records_are_selected(self):
        records = dj.parse_cache_records(fixture("buildx_du_verbose.txt"))
        chosen = dj.prunable_cache(records, NOW, 168)
        self.assertEqual(len(chosen), 180)
        self.assertEqual(sum(record.size for record in chosen), 20832596679)

    def test_nothing_recent_is_selected(self):
        records = dj.parse_cache_records(fixture("buildx_du_verbose.txt"))
        self.assertEqual(dj.prunable_cache(records, NOW, 24 * 365 * 100), [])

    def test_recent_child_protects_ancestor_records(self):
        old_time = NOW - timedelta(days=20)
        parent = dj.CacheRecord(
            id="parent1",
            created=old_time,
            reclaimable=True,
            shared=False,
            size=1000,
            parents=(),
            last_used="20 days ago",
        )
        child = dj.CacheRecord(
            id="child1",
            created=old_time,
            reclaimable=True,
            shared=False,
            size=500,
            parents=("parent1",),
            last_used="30 minutes ago",
        )
        chosen = dj.prunable_cache([parent, child], NOW, 168)
        self.assertEqual(chosen, [])


class SummarizeTests(unittest.TestCase):
    def test_summary_states_what_is_kept(self):
        preview = dj.Preview(
            cache_bytes=20832596679,
            cache_records=180,
            image_bytes=3558350010,
            image_count=19,
            kept_volumes_bytes=48020000,
            kept_volumes_count=2,
            kept_containers_bytes=98300,
            kept_containers_count=2,
            image_min_age_days=30,
            cache_min_age_hours=168,
        )
        text = dj.summarize(preview)
        self.assertIn("24.4 GB", text)
        self.assertIn("20.8 GB", text)
        self.assertIn("3.6 GB", text)
        self.assertIn("volumes are never touched", text)
        self.assertIn("30 days", text)
        self.assertIn("168 hours", text)


if __name__ == "__main__":
    unittest.main()
