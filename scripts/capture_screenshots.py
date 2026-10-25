#!/usr/bin/env python3
"""Script to render GTK windows and capture screenshots for UI/UX review."""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

import docker_janitor as dj

OUTPUT_DIR = os.path.join(dj.HERE, "docs", "screenshots")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def pump_events(iterations=30):
    for _ in range(iterations):
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.02)


def capture_window(window, filename):
    window.show_all()
    pump_events(50)

    gdk_win = window.get_window()
    if gdk_win is None:
        raise RuntimeError("Window has no GdkWindow")

    width = gdk_win.get_width()
    height = gdk_win.get_height()

    pixbuf = Gdk.pixbuf_get_from_window(gdk_win, 0, 0, width, height)
    if pixbuf is None:
        raise RuntimeError("Failed to capture pixbuf from window")

    out_path = os.path.join(OUTPUT_DIR, filename)
    pixbuf.savev(out_path, "png", [], [])
    print(f"Captured: {out_path} ({width}x{height})")
    return out_path


def main():
    Gtk.init([])

    # 1. Capture HUD Window (Ready State)
    preview = dj.Preview(
        cache_bytes=20832596679,
        cache_records=180,
        image_bytes=3558350010,
        image_count=19,
        kept_volumes_bytes=156200000,
        kept_volumes_count=6,
        kept_containers_bytes=98300,
        kept_containers_count=12,
    )
    hud_win = dj.JanitorHudWindow(preview=preview)
    hud_win.set_position(Gtk.WindowPosition.CENTER)
    capture_window(hud_win, "hud-window.png")
    hud_win.destroy()
    pump_events(10)

    # 2. Capture About Dialog (Main Tab)
    about_diag = dj.show_about_dialog()
    about_diag.set_position(Gtk.WindowPosition.CENTER)
    capture_window(about_diag, "about-dialog.png")

    # 3. Capture About Dialog (Credits Tab)
    def find_stack(w):
        if isinstance(w, Gtk.Stack):
            return w
        if isinstance(w, Gtk.Container):
            for c in w.get_children():
                res = find_stack(c)
                if res:
                    return res
        return None

    stack = find_stack(about_diag)
    if stack:
        for child in stack.get_children():
            name = stack.child_get_property(child, "name")
            title = stack.child_get_property(child, "title")
            if "credits" in str(name).lower() or "credits" in str(title).lower():
                stack.set_visible_child(child)
                break
        pump_events(30)
        capture_window(about_diag, "about-credits.png")

    about_diag.destroy()
    pump_events(10)

    print("All screenshots successfully captured!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
