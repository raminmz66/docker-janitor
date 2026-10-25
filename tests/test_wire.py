"""Task 7 tests: wiring the indicator menu to the preview/prune background worker."""

import os
import tempfile
import unittest

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

Gtk.init_check([])

import docker_janitor as dj


def drain_glib_events():
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)


class FakeDockerRunner:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        if self.should_fail:
            raise dj.DockerError("daemon unreachable")
        cmd = " ".join(args)
        if cmd == "info":
            return "ok"
        if cmd in ("system df", "system df -v"):
            return (
                "TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE\n"
                "Images          10        2         5.0GB     4.0GB\n"
                "Containers      2         0         10kB      10kB\n"
                "Local Volumes   1         0         1MB       1MB\n"
                "Build Cache     20        0         2.0GB     2.0GB\n"
            )
        if cmd == "images --format {{json .}}":
            return (
                '{"ID":"111111111111","Repository":"myrepo",'
                '"Tag":"latest","CreatedAt":"2020-01-01 00:00:00 +0000"}\n'
            )
        if cmd == "ps -aq":
            return ""
        if cmd == "buildx du --verbose":
            return (
                "ID: cache1\n"
                "Created at: 2020-01-01 00:00:00 +0000\n"
                "Reclaimable: true\n"
                "Shared: false\n"
                "Size: 2.0GB\n\n"
            )
        return "ok"


class WireAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log_path = os.path.join(self.tmp.name, "docker-janitor.log")
        self.config = dj.Config(image_min_age_days=30, cache_min_age_hours=168)
        self.toasts = []

    def tearDown(self):
        self.tmp.cleanup()

    def _notifier(self, title, msg):
        self.toasts.append((title, msg))

    def test_double_click_run_starts_only_one_job(self):
        docker = FakeDockerRunner()
        app = dj.JanitorApp()
        app._config = self.config
        app._runner = docker
        app._dialog_runner = lambda argv: False
        app._notifier = self._notifier
        app._log_path = self.log_path

        menu = dj.build_menu(app.on_run, app.quit_app)
        app._run_item = menu.get_children()[0]

        # First run starts worker
        first = app.on_run()
        self.assertTrue(first)
        self.assertFalse(app._run_item.get_sensitive())

        # Second run while running is rejected
        second = app.on_run()
        self.assertFalse(second)

        # Wait for worker thread to finish
        if app._worker_thread:
            app._worker_thread.join(timeout=2.0)
        drain_glib_events()

        self.assertFalse(app._running)
        self.assertTrue(app._run_item.get_sensitive())

    def test_run_opens_hud_immediately_in_scanning_state(self):
        docker = FakeDockerRunner()
        app = dj.JanitorApp()
        app._config = self.config
        app._runner = docker
        app._notifier = self._notifier
        app._log_path = self.log_path

        menu = dj.build_menu(app.on_run, app.quit_app)
        app._run_item = menu.get_children()[0]

        app.on_run()
        # Immediately after calling on_run, the window is already created in scanning mode
        self.assertIsNotNone(app._hud_window)
        self.assertTrue(app._hud_window._is_scanning)

        # After worker finishes and GLib events drain, it transitions to ready
        if app._worker_thread:
            app._worker_thread.join(timeout=2.0)
        drain_glib_events()

        self.assertFalse(app._hud_window._is_scanning)
        self.assertIn("Free", app._hud_window._clean_button.get_label())
        app._hud_window.destroy()

    def test_daemon_down_shows_toast_without_crashing(self):
        docker = FakeDockerRunner(should_fail=True)
        app = dj.JanitorApp()
        app._config = self.config
        app._runner = docker
        app._dialog_runner = lambda argv: True
        app._notifier = self._notifier
        app._log_path = self.log_path

        menu = dj.build_menu(app.on_run, app.quit_app)
        app._run_item = menu.get_children()[0]

        app.on_run()
        if app._worker_thread:
            app._worker_thread.join(timeout=2.0)
        drain_glib_events()

        self.assertTrue(len(self.toasts) >= 1)
        self.assertIn("daemon unreachable", self.toasts[0][1])
        self.assertTrue(app._run_item.get_sensitive())
        self.assertIsNotNone(app._hud_window)
        self.assertTrue(app._hud_window._is_error)
        self.assertEqual(app._hud_window._clean_button.get_label(), "Close")
        app._hud_window.destroy()

    def test_dismiss_during_scan_safely_ignores_finished_scan(self):
        docker = FakeDockerRunner()
        app = dj.JanitorApp()
        app._config = self.config
        app._runner = docker
        app._notifier = self._notifier
        app._log_path = self.log_path

        menu = dj.build_menu(app.on_run, app.quit_app)
        app._run_item = menu.get_children()[0]

        app.on_run()
        self.assertIsNotNone(app._hud_window)

        # User dismisses HUD immediately while worker is still running
        app._hud_window.on_escape_pressed()
        self.assertIsNone(app._hud_window)

        # Worker finishes later
        if app._worker_thread:
            app._worker_thread.join(timeout=2.0)
        drain_glib_events()

        # HUD remains None and app returns to idle state
        self.assertIsNone(app._hud_window)
        self.assertFalse(app._running)
        self.assertTrue(app._run_item.get_sensitive())

    def test_skip_in_hud_executes_no_prunes(self):
        docker = FakeDockerRunner()
        app = dj.JanitorApp()
        app._config = self.config
        app._runner = docker
        app._notifier = self._notifier
        app._log_path = self.log_path

        menu = dj.build_menu(app.on_run, app.quit_app)
        app._run_item = menu.get_children()[0]

        app.on_run()
        if app._worker_thread:
            app._worker_thread.join(timeout=2.0)
        drain_glib_events()

        # HUD should now be open
        self.assertIsNotNone(app._hud_window)

        # User presses Escape / dismisses HUD
        app._hud_window.on_escape_pressed()
        self.assertIsNone(app._hud_window)

        # Check no prune command was sent to docker
        for call in docker.calls:
            self.assertNotIn("prune", call)
        self.assertFalse(os.path.exists(self.log_path))
        self.assertTrue(app._run_item.get_sensitive())

    def test_clean_in_hud_executes_prune_and_logs(self):
        docker = FakeDockerRunner()
        app = dj.JanitorApp()
        app._config = self.config
        app._runner = docker
        app._notifier = self._notifier
        app._log_path = self.log_path

        menu = dj.build_menu(app.on_run, app.quit_app)
        app._run_item = menu.get_children()[0]

        app.on_run()
        if app._worker_thread:
            app._worker_thread.join(timeout=2.0)
        drain_glib_events()

        # HUD is open; user clicks the clean button
        self.assertIsNotNone(app._hud_window)
        app._hud_window._clean_button.clicked()

        if app._worker_thread:
            app._worker_thread.join(timeout=2.0)
        drain_glib_events()

        # Check prune command was sent
        prune_calls = [call for call in docker.calls if "prune" in call]
        self.assertTrue(len(prune_calls) >= 2)
        self.assertTrue(os.path.exists(self.log_path))
        self.assertTrue(len(self.toasts) >= 1)
        self.assertIn("reclaimed", self.toasts[0][1].lower())


if __name__ == "__main__":
    unittest.main()
