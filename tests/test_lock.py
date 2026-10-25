"""Task 1 tests: single-instance lock and the two-item menu."""

import os
import tempfile
import unittest

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

Gtk.init_check([])

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
    def test_menu_structure_contains_run_about_and_exit(self):
        about_called = []
        menu = docker_janitor.build_menu(
            on_run=lambda *_: None,
            on_about=lambda *_: about_called.append(True),
            on_exit=lambda *_: None,
        )
        children = menu.get_children()
        self.assertEqual(len(children), 4)

        run_item, about_item, sep_item, exit_item = children
        self.assertEqual(run_item.get_label(), "Run")
        self.assertEqual(about_item.get_label(), "About Docker Janitor")
        self.assertIsInstance(sep_item, Gtk.SeparatorMenuItem)
        self.assertEqual(exit_item.get_label(), "Exit")

        about_item.activate()
        self.assertEqual(about_called, [True])

    def test_menu_backward_compatible_with_two_arguments(self):
        exit_called = []
        menu = docker_janitor.build_menu(
            on_run=lambda *_: None,
            on_exit=lambda *_: exit_called.append(True),
        )
        children = menu.get_children()
        self.assertEqual(len(children), 4)
        exit_item = children[3]
        exit_item.activate()
        self.assertEqual(exit_called, [True])

    def test_run_item_starts_sensitive(self):
        menu = docker_janitor.build_menu(on_run=lambda *_: None, on_exit=lambda *_: None)
        run_item = menu.get_children()[0]
        self.assertTrue(run_item.get_sensitive())


if __name__ == "__main__":
    unittest.main()
