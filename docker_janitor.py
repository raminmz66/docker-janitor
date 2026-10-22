#!/usr/bin/env python3
"""Docker Janitor — preview Docker cleanup, then prune only if you say so.

The app is a tray indicator: click it, choose Run, review what would be
reclaimed, and press Continue to actually delete anything.
"""

import fcntl
import os
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
from gi.repository import Gtk  # noqa: E402

APP_ID = "docker-janitor"
HERE = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(HERE, "icons")
ICON_NAME = "docker-janitor"
ICON_FALLBACK = "edit-clear"


def lock_path():
    """Runtime lock lives in the session directory, cleaned up on logout."""
    base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
    return os.path.join(base, APP_ID + ".lock")


def acquire_lock(path):
    """Take an exclusive lock. Return the open handle, or None if taken."""
    handle = open(path, "a+")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    handle.truncate(0)
    handle.write(str(os.getpid()))
    handle.flush()
    return handle


def build_menu(on_run, on_exit):
    """Menu with exactly two entries; Run stays disabled until wired up."""
    menu = Gtk.Menu()

    run_item = Gtk.MenuItem(label="Run")
    run_item.set_sensitive(False)
    run_item.connect("activate", on_run)
    menu.append(run_item)

    exit_item = Gtk.MenuItem(label="Exit")
    exit_item.connect("activate", on_exit)
    menu.append(exit_item)

    menu.show_all()
    return menu


def icon_reference():
    """Prefer the bundled icon; fall back to a themed one while it is missing."""
    if os.path.exists(os.path.join(ICON_DIR, ICON_NAME + ".svg")):
        return ICON_NAME
    return ICON_FALLBACK


class JanitorApp:
    def __init__(self):
        self._indicator = None
        self._lock = None

    def build_indicator(self):
        indicator = AppIndicator.Indicator.new(
            APP_ID, icon_reference(), AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        if os.path.isdir(ICON_DIR):
            indicator.set_icon_theme_path(ICON_DIR)
        indicator.set_icon_full(icon_reference(), "Docker Janitor")
        indicator.set_menu(build_menu(self.on_run, self.quit_app))
        indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self._indicator = indicator
        return indicator

    def on_run(self, *_args):
        """Task 7 wires the preview/prune cycle in here."""
        return

    def quit_app(self, *_args):
        self._indicator = None
        Gtk.main_quit()


def main():
    handle = acquire_lock(lock_path())
    if handle is None:
        return 0  # another instance owns the panel icon

    app = JanitorApp()
    app._lock = handle
    Gtk.init([])
    app.build_indicator()
    Gtk.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
