"""Tests for the native GTK Popover HUD component."""

import unittest

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

Gtk.init_check([])

import docker_janitor as dj


class StorageProportionsTests(unittest.TestCase):
    def test_proportions_with_typical_values(self):
        # 20 GB cache, 5 GB images, 25 GB kept -> total 50 GB
        props = dj.calculate_storage_proportions(
            cache_bytes=20 * 10**9,
            image_bytes=5 * 10**9,
            kept_bytes=25 * 10**9,
        )
        self.assertAlmostEqual(props["cache"], 0.4, places=2)
        self.assertAlmostEqual(props["images"], 0.1, places=2)
        self.assertAlmostEqual(props["kept"], 0.5, places=2)

    def test_proportions_with_zero_bytes(self):
        props = dj.calculate_storage_proportions(0, 0, 0)
        self.assertEqual(props["cache"], 0.0)
        self.assertEqual(props["images"], 0.0)
        self.assertEqual(props["kept"], 1.0)

    def test_minimum_slice_visibility(self):
        # Very small image bytes (1 MB vs 100 GB) should have a small floor percentage
        props = dj.calculate_storage_proportions(
            cache_bytes=50 * 10**9,
            image_bytes=10**6,
            kept_bytes=50 * 10**9,
        )
        self.assertTrue(props["images"] >= 0.02)


class SegmentedBarWidgetTests(unittest.TestCase):
    def test_build_segmented_bar_returns_gtk_box(self):
        bar = dj.build_segmented_bar(
            cache_bytes=20 * 10**9,
            image_bytes=4 * 10**9,
            kept_bytes=10 * 10**9,
        )
        self.assertIsInstance(bar, Gtk.Box)
        children = bar.get_children()
        # Should contain 3 segments: cache, images, kept
        self.assertEqual(len(children), 3)


if __name__ == "__main__":
    unittest.main()
