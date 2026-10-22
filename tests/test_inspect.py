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

    def test_dangling_images_are_counted_separately(self):
        self.assertEqual(dj.dangling_images(self.images), [])


class CacheRecordTests(unittest.TestCase):
    def test_private_old_records_are_selected(self):
        records = dj.parse_cache_records(fixture("buildx_du_verbose.txt"))
        chosen = dj.prunable_cache(records, NOW, 168)
        self.assertEqual(len(chosen), 180)
        self.assertEqual(sum(record.size for record in chosen), 20832596679)

    def test_nothing_recent_is_selected(self):
        records = dj.parse_cache_records(fixture("buildx_du_verbose.txt"))
        self.assertEqual(dj.prunable_cache(records, NOW, 24 * 365 * 100), [])


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
