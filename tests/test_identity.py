"""Tests for project identity, metadata constants, and CLI flags."""

import io
import unittest
from unittest import mock

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

Gtk.init_check([])

import docker_janitor


class IdentityMetadataTests(unittest.TestCase):
    def test_version_and_metadata_constants(self):
        self.assertEqual(docker_janitor.__version__, "0.1.0")
        self.assertEqual(docker_janitor.__app_name__, "Docker Janitor")
        self.assertEqual(docker_janitor.__author__, "Ramin Maazallahi")
        self.assertEqual(docker_janitor.__email__, "r.mazallahi-ext@initiative-crm.com")
        self.assertEqual(docker_janitor.__license__, "MIT")
        self.assertEqual(
            docker_janitor.__website__, "https://github.com/raminmz66/docker-janitor"
        )


class CliFlagsTests(unittest.TestCase):
    def test_version_flag_prints_version_and_exits_zero(self):
        for flag in ["--version", "-v"]:
            with self.subTest(flag=flag):
                stdout = io.StringIO()
                with mock.patch("sys.stdout", stdout):
                    exit_code = docker_janitor.main([flag])
                self.assertEqual(exit_code, 0)
                output = stdout.getvalue().strip()
                self.assertEqual(output, "Docker Janitor 0.1.0")

    def test_help_flag_prints_usage_and_exits_zero(self):
        for flag in ["--help", "-h"]:
            with self.subTest(flag=flag):
                stdout = io.StringIO()
                with mock.patch("sys.stdout", stdout):
                    exit_code = docker_janitor.main([flag])
                self.assertEqual(exit_code, 0)
                output = stdout.getvalue()
                self.assertIn("Docker Janitor", output)
                self.assertIn("--version", output)
                self.assertIn("--help", output)

    @mock.patch("docker_janitor.acquire_lock")
    def test_cli_flags_do_not_attempt_lock_or_gtk_init(self, mock_lock):
        for flag in ["--version", "-v", "--help", "-h"]:
            with self.subTest(flag=flag):
                mock_lock.reset_mock()
                with mock.patch("sys.stdout", io.StringIO()):
                    docker_janitor.main([flag])
                mock_lock.assert_not_called()


class AboutDialogTests(unittest.TestCase):
    def test_show_about_dialog_creates_and_configures_dialog(self):
        dialog = docker_janitor.show_about_dialog()
        try:
            self.assertIsInstance(dialog, Gtk.AboutDialog)
            self.assertEqual(dialog.get_program_name(), "Docker Janitor")
            self.assertEqual(dialog.get_version(), "0.1.0")
            self.assertIn("Docker disk space", dialog.get_comments())
            self.assertEqual(dialog.get_copyright(), "© 2026 Ramin Maazallahi")
            self.assertEqual(
                dialog.get_website(), "https://github.com/raminmz66/docker-janitor"
            )
            self.assertEqual(dialog.get_website_label(), "GitHub Repository")
            self.assertEqual(dialog.get_license_type(), Gtk.License.MIT_X11)
            self.assertEqual(
                dialog.get_authors(),
                ["Ramin Maazallahi <r.mazallahi-ext@initiative-crm.com>"],
            )
            self.assertIsNotNone(dialog.get_logo())
        finally:
            dialog.destroy()


if __name__ == "__main__":
    unittest.main()
