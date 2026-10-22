"""Task 1 tests: single-instance lock and the two-item menu."""

import os
import tempfile
import unittest

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

import docker_janitor


class LockTests(unittest.TestCase):
    def test_second_acquire_fails_while_first_is_held(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "janitor.lock")

            first = docker_janitor.acquire_lock(path)
            self.assertIsNotNone(first, "first acquire should succeed")

            second = docker_janitor.acquire_lock(path)
            self.assertIsNone(second, "second acquire must be refused")

            first.close()

            third = docker_janitor.acquire_lock(path)
            self.assertIsNotNone(third, "lock must be reusable after release")
            third.close()


class MenuTests(unittest.TestCase):
    def test_menu_contains_only_run_and_exit(self):
        menu = docker_janitor.build_menu(on_run=lambda *_: None, on_exit=lambda *_: None)
        labels = [child.get_label() for child in menu.get_children()]
        self.assertEqual(labels, ["Run", "Exit"])

    def test_run_item_starts_insensitive(self):
        menu = docker_janitor.build_menu(on_run=lambda *_: None, on_exit=lambda *_: None)
        run_item = menu.get_children()[0]
        self.assertFalse(run_item.get_sensitive())


if __name__ == "__main__":
    unittest.main()
