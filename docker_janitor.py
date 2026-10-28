#!/usr/bin/env python3
"""Docker Janitor — preview Docker cleanup, then prune only if you say so.

The app is a tray indicator: click it, choose Run, review what would be
reclaimed, and press Continue to actually delete anything.
"""

import fcntl
import json
import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk  # noqa: E402

APP_ID = "docker-janitor"
__version__ = "0.1.0"
__app_name__ = "Docker Janitor"
__author__ = "Ramin Maazallahi"
__email__ = "r.mazallahi-ext@initiative-crm.com"
__license__ = "MIT"
__website__ = "https://github.com/raminmz66/docker-janitor"
__description__ = (
    "A lightweight Linux desktop indicator for previewing and safely cleaning Docker disk space."
)
HERE = os.path.dirname(os.path.abspath(__file__))
ICON_DIR = os.path.join(HERE, "icons")
ICON_NAME = "docker-janitor"
ICON_FALLBACK = "edit-clear"

DEFAULT_IMAGE_MIN_AGE_DAYS = 30
DEFAULT_CACHE_MIN_AGE_HOURS = 168
CONFIG_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
    APP_ID,
    "config.env",
)
LOG_PATH = os.path.join(
    os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"),
    APP_ID + ".log",
)


@dataclass(frozen=True)
class Config:
    """Age thresholds; anything younger than this is left alone."""

    image_min_age_days: int = DEFAULT_IMAGE_MIN_AGE_DAYS
    cache_min_age_hours: int = DEFAULT_CACHE_MIN_AGE_HOURS


def _positive_int(raw, default):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return value if value >= 0 else default


def load_config(path):
    """Read key=value pairs; anything missing or malformed keeps its default."""
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
    except OSError:
        return Config()

    values = {}
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()

    defaults = Config()
    return Config(
        image_min_age_days=_positive_int(
            values.get("IMAGE_MIN_AGE_DAYS"), defaults.image_min_age_days
        ),
        cache_min_age_hours=_positive_int(
            values.get("CACHE_MIN_AGE_HOURS"), defaults.cache_min_age_hours
        ),
    )


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


def show_about_dialog(parent=None):
    """Display the native GTK About dialog for Docker Janitor."""
    dialog = Gtk.AboutDialog()
    if parent:
        dialog.set_transient_for(parent)
        dialog.set_modal(True)
    dialog.set_program_name(__app_name__)
    dialog.set_version(__version__)
    dialog.set_comments(__description__)
    dialog.set_copyright(f"© 2026 {__author__}")
    dialog.set_website(__website__)
    dialog.set_website_label("GitHub Repository")
    dialog.set_authors([f"{__author__} <{__email__}>"])
    dialog.set_license_type(Gtk.License.MIT_X11)

    icon_path = os.path.join(ICON_DIR, ICON_NAME + ".svg")
    if os.path.exists(icon_path):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, 96, 96, True)
            dialog.set_logo(pixbuf)
        except Exception:
            pass

    dialog.connect("response", lambda d, *_: d.destroy())
    dialog.show_all()
    dialog.present()
    return dialog


def build_menu(on_run, on_about=None, on_exit=None):
    """Menu with Run, About Docker Janitor, Separator, and Exit."""
    if on_exit is None and callable(on_about):
        # Backward compatibility if called as build_menu(on_run, on_exit)
        on_exit = on_about
        on_about = None

    if on_about is None:
        def _default_on_about(*_):
            return show_about_dialog()

        on_about = _default_on_about

    menu = Gtk.Menu()

    run_item = Gtk.MenuItem(label="Run")
    run_item.set_sensitive(True)
    run_item.connect("activate", on_run)
    menu.append(run_item)

    about_item = Gtk.MenuItem(label="About Docker Janitor")
    about_item.set_sensitive(True)
    about_item.connect("activate", on_about)
    menu.append(about_item)

    sep_item = Gtk.SeparatorMenuItem()
    menu.append(sep_item)

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


_SIZE_UNITS = {"B": 1, "KB": 10**3, "MB": 10**6, "GB": 10**9, "TB": 10**12}
_SIZE_RE = re.compile(r"([\d.]+)\s*([kKMGT]?B)")
_TIMESTAMP_RE = re.compile(
    r"(\d{4}-\d\d-\d\d)\s+(\d\d:\d\d:\d\d)(?:\.(\d+))?(?:\s*([+-]\d{4}))?"
)


def parse_size(text):
    """Docker's human sizes use SI units, so 1 GB means 10^9 bytes."""
    if not text:
        return 0
    match = _SIZE_RE.search(text)
    if not match:
        return 0
    unit = match.group(2).upper()
    try:
        return int(round(float(match.group(1)) * _SIZE_UNITS[unit]))
    except KeyError:
        return 0


def local_timezone():
    return datetime.now().astimezone().tzinfo


def parse_timestamp(text):
    """Accept Docker's variants: with/without fraction, with/without offset."""
    match = _TIMESTAMP_RE.search(text or "")
    if not match:
        raise ValueError("unparseable timestamp: %r" % (text,))
    stamp = datetime.strptime("%s %s" % (match.group(1), match.group(2)), "%Y-%m-%d %H:%M:%S")
    if match.group(3):
        stamp = stamp.replace(microsecond=int((match.group(3) + "000000")[:6]))
    offset = match.group(4)
    if offset:
        sign = 1 if offset[0] == "+" else -1
        zone = timezone(
            sign * timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5]))
        )
        return stamp.replace(tzinfo=zone)
    return stamp.replace(tzinfo=local_timezone())


def human_bytes(value):
    for unit, factor in (("TB", 10**12), ("GB", 10**9), ("MB", 10**6), ("kB", 10**3)):
        if value >= factor:
            return "%.1f %s" % (value / factor, unit)
    return "%d B" % value


def calculate_storage_proportions(cache_bytes, image_bytes, kept_bytes):
    """Return fractions of total storage with a floor so non-zero slices remain visible."""
    total = cache_bytes + image_bytes + kept_bytes
    if total <= 0:
        return {"cache": 0.0, "images": 0.0, "kept": 1.0}

    raw = {
        "cache": cache_bytes / total,
        "images": image_bytes / total,
        "kept": kept_bytes / total,
    }
    min_floor = 0.02
    has_min = {k: max(v, min_floor) if v > 0 else 0.0 for k, v in raw.items()}
    diff = sum(has_min.values()) - 1.0
    if diff > 0:
        largest_key = max(has_min.keys(), key=lambda k: raw[k])
        has_min[largest_key] = max(min_floor, has_min[largest_key] - diff)

    return has_min


HUD_CSS = """
window.janitor-hud {
    background-color: transparent;
}
.janitor-card {
    background-color: @theme_base_color;
    color: @theme_text_color;
    border: 1px solid alpha(@theme_text_color, 0.18);
    border-radius: 14px;
    padding: 16px 18px;
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.28);
}
.janitor-hero-number {
    font-size: 32px;
    font-weight: 800;
    color: #0db7ed;
}
.janitor-segmented-bar {
    border-radius: 6px;
    background-color: alpha(@theme_text_color, 0.08);
    min-height: 10px;
}
.bar-segment-cache {
    background-color: #0db7ed;
    background-image: none;
}
.bar-segment-images {
    background-color: #ff9f0a;
    background-image: none;
}
.bar-segment-kept {
    background-color: alpha(@theme_text_color, 0.25);
    background-image: none;
}
.bar-segment-first {
    border-top-left-radius: 5px;
    border-bottom-left-radius: 5px;
}
.bar-segment-last {
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
}
.bar-legend-cache {
    color: #0db7ed;
    font-size: 11px;
    font-weight: 600;
}
.bar-legend-images {
    color: #ff9f0a;
    font-size: 11px;
    font-weight: 600;
}
.janitor-title {
    font-weight: 700;
    font-size: 13px;
}
.dim-label {
    opacity: 0.65;
    font-size: 11.5px;
}
.janitor-badge {
    background-color: rgba(52, 199, 89, 0.12);
    border: 1px solid rgba(52, 199, 89, 0.3);
    border-radius: 8px;
    padding: 7px 11px;
}
.janitor-badge label {
    color: @theme_text_color;
    font-size: 11px;
    font-weight: 500;
}
button.janitor-close-btn,
button.janitor-info-btn,
button.janitor-header-btn {
    border: none;
    background: transparent;
    background-image: none;
    box-shadow: none;
    color: alpha(@theme_text_color, 0.5);
    border-radius: 6px;
    padding: 3px 5px;
}
button.janitor-close-btn:hover,
button.janitor-info-btn:hover,
button.janitor-header-btn:hover {
    background-color: alpha(@theme_text_color, 0.08);
    color: @theme_text_color;
}
.janitor-version-badge {
    color: alpha(@theme_text_color, 0.5);
    font-size: 10px;
    font-weight: 500;
    padding: 1px 5px;
    border-radius: 4px;
    background-color: alpha(@theme_text_color, 0.08);
}
button.janitor-btn-primary {
    background-color: #0db7ed;
    background-image: none;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    box-shadow: 0 2px 8px rgba(13, 183, 237, 0.4);
}
button.janitor-btn-primary:hover {
    background-color: #09a5d7;
    background-image: none;
}
button.janitor-btn-primary:active {
    background-color: #088db8;
    background-image: none;
}
button.janitor-btn-primary:disabled {
    background-color: alpha(@theme_text_color, 0.12);
    background-image: none;
    box-shadow: none;
}
button.janitor-btn-primary label {
    color: #ffffff;
    font-weight: 700;
    font-size: 13px;
}
button.janitor-btn-primary:disabled label {
    color: alpha(@theme_text_color, 0.4);
}
"""

_CSS_LOADED = False


def ensure_hud_css():
    global _CSS_LOADED
    if _CSS_LOADED:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(HUD_CSS.encode("utf-8"))
    screen = Gdk.Screen.get_default()
    if screen:
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    _CSS_LOADED = True


def build_segmented_bar(cache_bytes, image_bytes, kept_bytes):
    ensure_hud_css()
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
    box.get_style_context().add_class("janitor-segmented-bar")
    box.set_size_request(300, 10)

    props = calculate_storage_proportions(cache_bytes, image_bytes, kept_bytes)

    segments = [
        ("cache", "bar-segment-cache"),
        ("images", "bar-segment-images"),
        ("kept", "bar-segment-kept"),
    ]
    for idx, (key, class_name) in enumerate(segments):
        seg = Gtk.Box()
        seg_ctx = seg.get_style_context()
        seg_ctx.add_class(class_name)
        if idx == 0:
            seg_ctx.add_class("bar-segment-first")
        if idx == len(segments) - 1:
            seg_ctx.add_class("bar-segment-last")
        box.pack_start(seg, True, True, 0)
        seg.set_size_request(max(4, int(300 * props[key])), 10)

    return box


class JanitorHudWindow(Gtk.Window):
    def __init__(
        self,
        preview=None,
        on_clean=None,
        on_close=None,
        on_exit_app=None,
        on_about=None,
    ):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        ensure_hud_css()

        self.preview = preview
        self._is_scanning = preview is None
        self._is_error = False
        self.on_clean_callback = on_clean
        self.on_close_callback = on_close
        self.on_exit_app_callback = on_exit_app
        self.on_about = on_about

        self.set_decorated(False)
        self.set_type_hint(Gdk.WindowTypeHint.POPUP_MENU)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_resizable(False)

        screen = self.get_screen()
        if screen:
            visual = screen.get_rgba_visual()
            if visual and screen.is_composited():
                self.set_visual(visual)
        self.set_app_paintable(True)
        self.get_style_context().add_class("janitor-hud")

        self.connect("key-press-event", self._on_key_press)
        self.connect("focus-out-event", self._on_focus_out)

        self._build_ui()

    def _on_info_clicked(self):
        if self.on_about:
            self.on_about()
        else:
            show_about_dialog(parent=self)

    def _build_ui(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        card.get_style_context().add_class("janitor-card")
        self.add(card)

        # Header
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        icon_path = os.path.join(ICON_DIR, ICON_NAME + ".svg")
        if os.path.exists(icon_path):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(icon_path, 20, 20, True)
                icon_img = Gtk.Image.new_from_pixbuf(pixbuf)
            except Exception:
                icon_img = Gtk.Image.new_from_icon_name("edit-clear", Gtk.IconSize.MENU)
        else:
            icon_img = Gtk.Image.new_from_icon_name("edit-clear", Gtk.IconSize.MENU)

        title_box.pack_start(icon_img, False, False, 0)
        title_lbl = Gtk.Label(label="Docker Janitor")
        title_lbl.get_style_context().add_class("janitor-title")
        title_box.pack_start(title_lbl, False, False, 0)

        version_lbl = Gtk.Label(label=f"v{__version__}")
        version_lbl.get_style_context().add_class("janitor-version-badge")
        title_box.pack_start(version_lbl, False, False, 0)

        header.pack_start(title_box, False, False, 0)

        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)

        info_icon = Gtk.Image.new_from_icon_name("help-about-symbolic", Gtk.IconSize.MENU)
        self._info_button = Gtk.Button()
        self._info_button.set_image(info_icon)
        self._info_button.get_style_context().add_class("janitor-header-btn")
        self._info_button.set_relief(Gtk.ReliefStyle.NONE)
        self._info_button.set_tooltip_text("About Docker Janitor")
        self._info_button.connect("clicked", lambda *_: self._on_info_clicked())
        actions_box.pack_start(self._info_button, False, False, 0)

        close_icon = Gtk.Image.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)
        close_btn = Gtk.Button()
        close_btn.set_image(close_icon)
        close_btn.get_style_context().add_class("janitor-header-btn")
        close_btn.set_relief(Gtk.ReliefStyle.NONE)
        close_btn.set_tooltip_text("Dismiss")
        close_btn.connect("clicked", lambda *_: self.on_escape_pressed())
        actions_box.pack_start(close_btn, False, False, 0)

        header.pack_end(actions_box, False, False, 0)
        card.pack_start(header, False, False, 0)

        # Hero Stat
        hero_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        hero_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hero_row.set_halign(Gtk.Align.CENTER)

        self._spinner = Gtk.Spinner()
        hero_row.pack_start(self._spinner, False, False, 0)

        self._hero_label = Gtk.Label()
        self._hero_label.get_style_context().add_class("janitor-hero-number")
        hero_row.pack_start(self._hero_label, False, False, 0)
        hero_box.pack_start(hero_row, False, False, 0)

        self._hero_sub = Gtk.Label()
        self._hero_sub.get_style_context().add_class("dim-label")
        hero_box.pack_start(self._hero_sub, False, False, 0)
        card.pack_start(hero_box, False, False, 0)

        # Bar container
        self._bar_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        card.pack_start(self._bar_container, False, False, 0)

        # Legend container
        self._legend_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        card.pack_start(self._legend_box, False, False, 0)

        # Safety badge
        self._badge_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._badge_box.get_style_context().add_class("janitor-badge")
        self._badge_lbl = Gtk.Label()
        self._badge_box.pack_start(self._badge_lbl, False, False, 0)
        card.pack_start(self._badge_box, False, False, 0)

        # Primary Action Button
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._clean_button = Gtk.Button()
        self._clean_button.get_style_context().add_class("janitor-btn-primary")
        self._clean_button.connect("clicked", self._on_clean_clicked)
        actions.pack_end(self._clean_button, True, True, 0)
        card.pack_start(actions, False, False, 0)

        if self.preview is not None:
            self.set_preview(self.preview)
        else:
            self._set_scanning_state()

    def _set_scanning_state(self):
        self._is_scanning = True
        self._spinner.start()
        self._spinner.show()
        self._hero_label.set_text("Scanning...")
        self._hero_sub.set_text("Inspecting Docker storage...")

        # Placeholder bar
        for child in self._bar_container.get_children():
            self._bar_container.remove(child)
        placeholder = Gtk.Box()
        placeholder.get_style_context().add_class("bar-segment-kept")
        placeholder.set_size_request(300, 10)
        self._bar_container.pack_start(placeholder, True, True, 0)
        self._bar_container.show_all()

        for child in self._legend_box.get_children():
            self._legend_box.remove(child)

        self._badge_lbl.set_text("🛡️ Checking container & volume safety...")
        self._clean_button.set_label("Calculating Space...")
        self._clean_button.set_sensitive(False)

    def set_preview(self, preview):
        self.preview = preview
        self._is_scanning = False
        self._is_error = False
        self._spinner.stop()
        self._spinner.hide()

        self._hero_label.set_text(human_bytes(preview.total_bytes))
        self._hero_sub.set_text("Reclaimable without affecting active projects")

        # Bar
        for child in self._bar_container.get_children():
            self._bar_container.remove(child)
        kept_bytes = preview.kept_volumes_bytes + preview.kept_containers_bytes
        bar = build_segmented_bar(preview.cache_bytes, preview.image_bytes, kept_bytes)
        self._bar_container.pack_start(bar, True, True, 0)
        self._bar_container.show_all()

        # Legend
        for child in self._legend_box.get_children():
            self._legend_box.remove(child)
        cache_lbl = Gtk.Label(label="● Cache: %s" % human_bytes(preview.cache_bytes))
        cache_lbl.get_style_context().add_class("bar-legend-cache")
        images_lbl = Gtk.Label(label="● Images: %s" % human_bytes(preview.image_bytes))
        images_lbl.get_style_context().add_class("bar-legend-images")
        self._legend_box.pack_start(cache_lbl, False, False, 0)
        self._legend_box.pack_start(images_lbl, False, False, 0)
        self._legend_box.show_all()

        # Badge
        badge_text = "🛡️ Protected: %d volumes (%s) & %d containers safe" % (
            preview.kept_volumes_count,
            human_bytes(preview.kept_volumes_bytes),
            preview.kept_containers_count,
        )
        self._badge_lbl.set_text(badge_text)

        # Button
        if preview.empty:
            self._clean_button.set_label("No Cleanup Needed")
            self._clean_button.set_sensitive(False)
        else:
            self._clean_button.set_label("Free %s Now" % human_bytes(preview.total_bytes))
            self._clean_button.set_sensitive(True)

    def set_error(self, message):
        self._is_scanning = False
        self._is_error = True
        self._spinner.stop()
        self._spinner.hide()

        self._hero_label.set_text("Docker Unavailable")
        self._hero_sub.set_text(message)

        for child in self._bar_container.get_children():
            self._bar_container.remove(child)
        for child in self._legend_box.get_children():
            self._legend_box.remove(child)

        self._badge_lbl.set_text("⚠️ Could not communicate with Docker daemon")
        self._clean_button.set_label("Close")
        self._clean_button.set_sensitive(True)

    def position_near_tray(self):
        display = Gdk.Display.get_default()
        if not display:
            return
        monitor = display.get_primary_monitor() or (
            display.get_n_monitors() > 0 and display.get_monitor(0)
        )
        if not monitor:
            return
        workarea = monitor.get_workarea()
        self.show_all()
        alloc = self.get_allocation()
        win_w = max(alloc.width, 340)
        x = workarea.x + workarea.width - win_w - 16
        y = workarea.y + 36
        self.move(max(0, x), max(0, y))

    def on_escape_pressed(self):
        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.on_escape_pressed()
            return True
        return False

    def _on_focus_out(self, widget, event):
        self.on_escape_pressed()
        return False

    def _on_clean_clicked(self, button):
        if self._is_error:
            self.on_escape_pressed()
            return
        button.set_sensitive(False)
        button.set_label("Cleaning up...")
        if self.on_clean_callback:
            self.on_clean_callback()


def parse_system_df(text):
    """Turn `docker system df` into {images, containers, volumes, cache} totals."""
    result = {}
    for raw in (text or "").splitlines():
        parts = raw.split()
        if len(parts) < 5 or parts[0] not in ("Images", "Containers", "Local", "Build"):
            continue
        if parts[0] == "Local" and len(parts) >= 6:
            key, total, active, size, reclaimable = (
                "volumes",
                parts[2],
                parts[3],
                parts[4],
                parts[5],
            )
        elif parts[0] == "Build" and len(parts) >= 6:
            key, total, active, size, reclaimable = (
                "cache",
                parts[2],
                parts[3],
                parts[4],
                parts[5],
            )
        else:
            key, total, active, size, reclaimable = (
                parts[0].lower(),
                parts[1],
                parts[2],
                parts[3],
                parts[4],
            )
        result[key] = {
            "total": _int_or_zero(total),
            "active": _int_or_zero(active),
            "size": parse_size(size),
            "reclaimable": parse_size(reclaimable),
        }
    return result


def _int_or_zero(text):
    try:
        return int(text)
    except (TypeError, ValueError):
        return 0


@dataclass(frozen=True)
class ImageRow:
    id: str
    repository: str
    tag: str
    created: datetime


@dataclass(frozen=True)
class CacheRecord:
    id: str
    created: datetime
    reclaimable: bool
    shared: bool
    size: int
    parents: tuple = ()
    last_used: str = ""


def parse_images(text):
    """One JSON object per line, as produced by `docker images --format '{{json .}}'`."""
    rows = []
    for raw in (text or "").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
            rows.append(
                ImageRow(
                    id=payload.get("ID", ""),
                    repository=payload.get("Repository", ""),
                    tag=payload.get("Tag", ""),
                    created=parse_timestamp(payload.get("CreatedAt", "")),
                )
            )
        except (ValueError, TypeError, KeyError):
            continue
    return rows


def parse_used_ids(text):
    """Image IDs and repository/tag references currently referenced by any container."""
    used = set()
    for raw in (text or "").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split("|||")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part.startswith("sha256:"):
                used.add(part[7:19])
            elif len(part) == 64 and all(c in "0123456789abcdefABCDEF" for c in part):
                used.add(part[:12])
            else:
                used.add(part)
    return used


def parse_unique_sizes(text):
    """IMAGE ID -> UNIQUE SIZE from the Images table of `docker system df -v`."""
    sizes = {}
    in_table = False
    for raw in (text or "").splitlines():
        if raw.startswith("REPOSITORY"):
            in_table = True
            continue
        if not in_table:
            continue
        if not raw.strip():
            in_table = False
            continue
        columns = re.split(r"\s{2,}", raw.strip())
        if len(columns) < 8:
            continue
        sizes[columns[2]] = parse_size(columns[-2])
    return sizes


def parse_cache_records(text):
    """Paragraphs from `docker buildx du --verbose`."""
    records = []
    current = {}
    parents = []

    def flush():
        if current.get("created") is not None and current.get("size") is not None:
            records.append(
                CacheRecord(
                    id=current.get("id", ""),
                    created=current["created"],
                    reclaimable=current.get("reclaimable", False),
                    shared=current.get("shared", False),
                    size=current["size"],
                    parents=tuple(parents),
                    last_used=current.get("last_used", ""),
                )
            )
            current.clear()
            parents.clear()

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith("- "):
            parents.append(line[2:].strip())
            continue
        label, _sep, value = line.partition(":")
        value = value.strip()
        label = label.strip()
        if label == "ID":
            current["id"] = value
        elif label == "Created at":
            try:
                current["created"] = parse_timestamp(value)
            except ValueError:
                current["created"] = None
        elif label == "Last used":
            current["last_used"] = value
        elif label == "Reclaimable":
            current["reclaimable"] = value == "true"
        elif label == "Shared":
            current["shared"] = value == "true"
        elif label == "Size":
            current["size"] = parse_size(value)
    flush()
    return records


def parse_image_ids(text):
    """Parse newline-separated image IDs as produced by `docker images -q`."""
    if not text:
        return set()
    return {line.strip() for line in text.splitlines() if line.strip()}


def _matches_eligible_ids(image_id, eligible_ids):
    """Check if image_id matches any eligible ID (prefix or exact, ignoring sha256:)."""
    if eligible_ids is None:
        return True
    if not eligible_ids:
        return False
    clean_id = (
        image_id.removeprefix("sha256:")
        if hasattr(image_id, "removeprefix")
        else (image_id[7:] if image_id.startswith("sha256:") else image_id)
    )
    for eid in eligible_ids:
        clean_eid = (
            eid.removeprefix("sha256:")
            if hasattr(eid, "removeprefix")
            else (eid[7:] if eid.startswith("sha256:") else eid)
        )
        if clean_id.startswith(clean_eid) or clean_eid.startswith(clean_id):
            return True
    return False


def unused_images(images, used_ids, now, min_age_days, eligible_ids=None):
    """Tagged images no container references and older than the threshold."""
    cutoff = now - timedelta(days=min_age_days)
    return [
        image
        for image in images
        if image.id not in used_ids
        and image.repository not in used_ids
        and ("%s:%s" % (image.repository, image.tag)) not in used_ids
        and not (image.repository == "<none>" and image.tag == "<none>")
        and (
            _matches_eligible_ids(image.id, eligible_ids)
            if eligible_ids is not None
            else image.created < cutoff
        )
    ]


def dangling_images(images):
    return [
        image
        for image in images
        if image.repository == "<none>" and image.tag == "<none>"
    ]


def _is_cache_recent(last_used, created, now, min_age_hours):
    if not last_used:
        return created is not None and created >= (now - timedelta(hours=min_age_hours))
    text = last_used.lower().strip()
    if any(w in text for w in ("just now", "second", "minute", "an hour", "a minute")):
        return True
    m = re.search(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", text)
    if m:
        count, unit = int(m.group(1)), m.group(2)
        unit_hours = {
            "second": 1 / 3600,
            "minute": 1 / 60,
            "hour": 1,
            "day": 24,
            "week": 168,
            "month": 720,
            "year": 8760,
        }
        approx_hours = count * unit_hours.get(unit, 1)
        return approx_hours < min_age_hours
    return created is not None and created >= (now - timedelta(hours=min_age_hours))


def prunable_cache(records, now, min_age_hours):
    """Reclaimable records whose dependency subtrees are older than the threshold."""
    by_id = {r.id: r for r in records}
    protected = {
        r.id
        for r in records
        if not (
            r.reclaimable
            and not r.shared
            and not _is_cache_recent(r.last_used, r.created, now, min_age_hours)
        )
    }
    stack = list(protected)
    while stack:
        curr_id = stack.pop()
        curr = by_id.get(curr_id)
        if not curr:
            continue
        for parent_id in curr.parents:
            if parent_id in by_id and parent_id not in protected:
                protected.add(parent_id)
                stack.append(parent_id)

    return [r for r in records if r.id not in protected]


@dataclass(frozen=True)
class Preview:
    cache_bytes: int = 0
    cache_records: int = 0
    image_bytes: int = 0
    image_count: int = 0
    dangling_bytes: int = 0
    dangling_count: int = 0
    kept_volumes_bytes: int = 0
    kept_volumes_count: int = 0
    kept_containers_bytes: int = 0
    kept_containers_count: int = 0
    image_min_age_days: int = DEFAULT_IMAGE_MIN_AGE_DAYS
    cache_min_age_hours: int = DEFAULT_CACHE_MIN_AGE_HOURS
    estimated: bool = False

    @property
    def total_bytes(self):
        return self.cache_bytes + self.image_bytes + self.dangling_bytes

    @property
    def empty(self):
        return self.total_bytes == 0


def summarize(preview):
    """Plain-language text for the confirmation dialog."""
    lines = ["Docker Janitor can free about %s." % human_bytes(preview.total_bytes), ""]
    lines.append(
        "Build cache: %s (%d entries older than %d hours)"
        % (human_bytes(preview.cache_bytes), preview.cache_records, preview.cache_min_age_hours)
    )
    lines.append(
        "Unused images: %s (%d images older than %d days)"
        % (human_bytes(preview.image_bytes), preview.image_count, preview.image_min_age_days)
    )
    if preview.dangling_count:
        lines.append(
            "Dangling images: %s (%d)"
            % (human_bytes(preview.dangling_bytes), preview.dangling_count)
        )
    lines.append("")
    lines.append(
        "Kept: volumes are never touched (%d, %s); containers are kept (%d, %s)."
        % (
            preview.kept_volumes_count,
            human_bytes(preview.kept_volumes_bytes),
            preview.kept_containers_count,
            human_bytes(preview.kept_containers_bytes),
        )
    )
    if preview.estimated:
        lines.append("")
        lines.append("Some sizes are estimates; Docker reports them as shared layers.")
    return "\n".join(lines)


class DockerError(RuntimeError):
    """Docker refused a command or is not reachable."""


def run_docker(*args):
    """Run a docker subcommand and return stdout, or raise DockerError."""
    try:
        done = subprocess.run(
            ("docker",) + args, capture_output=True, text=True, timeout=180
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DockerError(str(exc))
    if done.returncode != 0:
        raise DockerError((done.stderr or "").strip() or "docker %s failed" % (args[0],))
    return done.stdout


def collect_preview(config, runner=run_docker, now=None):
    """Read-only snapshot of what a prune would free. Deletes nothing."""
    runner("info")

    df = parse_system_df(runner("system", "df"))
    images = parse_images(runner("images", "--format", "{{json .}}"))
    container_ids = [line.strip() for line in runner("ps", "-aq").split() if line.strip()]
    used = set()
    if container_ids:
        used = parse_used_ids(
            runner(
                "container",
                "inspect",
                "--format",
                "{{.Image}}|||{{.Config.Image}}",
                *container_ids,
            )
        )
    unique = parse_unique_sizes(runner("system", "df", "-v"))
    if now is None:
        now = datetime.now().astimezone()

    eligible_ids = None
    try:
        raw_ids = runner(
            "images",
            "-a",
            "--filter",
            "until=%dh" % (config.image_min_age_days * 24),
            "-q",
        )
        eligible_ids = parse_image_ids(raw_ids)
    except DockerError:
        eligible_ids = None

    old_images = unused_images(
        images, used, now, config.image_min_age_days, eligible_ids=eligible_ids
    )
    dangling = dangling_images(images)

    estimated = False
    try:
        records = parse_cache_records(runner("buildx", "du", "--verbose"))
        prunable = prunable_cache(records, now, config.cache_min_age_hours)
        cache_bytes, cache_count = sum(r.size for r in prunable), len(prunable)
    except DockerError:
        # Older Docker without buildx: fall back to the summary figure.
        cache_bytes = df.get("cache", {}).get("reclaimable", 0)
        cache_count = 0
        estimated = True

    return Preview(
        cache_bytes=cache_bytes,
        cache_records=cache_count,
        image_bytes=sum(unique.get(image.id, 0) for image in old_images),
        image_count=len(old_images),
        dangling_bytes=sum(unique.get(image.id, 0) for image in dangling),
        dangling_count=len(dangling),
        kept_volumes_bytes=df.get("volumes", {}).get("size", 0),
        kept_volumes_count=df.get("volumes", {}).get("total", 0),
        kept_containers_bytes=df.get("containers", {}).get("size", 0),
        kept_containers_count=df.get("containers", {}).get("total", 0),
        image_min_age_days=config.image_min_age_days,
        cache_min_age_hours=config.cache_min_age_hours,
        estimated=estimated,
    )


def show_toast(title, message, runner=None):
    """Post a desktop notification using notify-send."""
    if runner is None:
        runner = subprocess.run
    try:
        runner(["notify-send", "-a", APP_ID, title, message])
    except OSError:
        pass


def _run_zenity(argv):
    try:
        return subprocess.run(argv).returncode
    except OSError:
        return 1


def ask_continue(preview, runner=_run_zenity):
    """True only when the user pressed Continue. Closing the dialog is a Skip."""
    argv = [
        "zenity",
        "--question",
        "--title=Docker Janitor",
        "--ok-label=Continue",
        "--cancel-label=Skip",
        "--width=460",
        "--text=" + summarize(preview),
    ]
    return runner(argv) == 0


def prune_commands(config):
    """Safe prune commands: only build cache and images, never volumes or containers."""
    return [
        ["builder", "prune", "-af", "--filter", "until=%dh" % config.cache_min_age_hours],
        ["image", "prune", "-f"],
        ["image", "prune", "-af", "--filter", "until=%dh" % (config.image_min_age_days * 24)],
    ]


@dataclass(frozen=True)
class Report:
    reclaimed_bytes: int
    before_bytes: int
    after_bytes: int
    timestamp: datetime = field(default_factory=lambda: datetime.now().astimezone())


def run_prune(cmds, runner=run_docker):
    """Execute the prune commands and return before/after stats."""
    before_df = parse_system_df(runner("system", "df"))
    for cmd in cmds:
        runner(*cmd)
    after_df = parse_system_df(runner("system", "df"))

    before_bytes = sum(item["size"] for item in before_df.values())
    after_bytes = sum(item["size"] for item in after_df.values())
    reclaimed_bytes = max(0, before_bytes - after_bytes)

    return Report(
        reclaimed_bytes=reclaimed_bytes,
        before_bytes=before_bytes,
        after_bytes=after_bytes,
    )


def log_report(report, path=LOG_PATH):
    """Append a timestamped summary of reclaimed space to the log file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(
            "%s reclaimed %s (before: %s, after: %s)\n"
            % (
                report.timestamp.isoformat(),
                human_bytes(report.reclaimed_bytes),
                human_bytes(report.before_bytes),
                human_bytes(report.after_bytes),
            )
        )


def notify_report(report, notifier=show_toast):
    """Post a desktop notification with the cleanup result."""
    if report.reclaimed_bytes == 0:
        msg = "Docker storage is already clean (0 B reclaimed)."
    else:
        msg = "Docker Janitor reclaimed %s." % human_bytes(report.reclaimed_bytes)
    notifier("Docker Janitor", msg)


class JanitorApp:

    def __init__(
        self,
        config=None,
        runner=run_docker,
        dialog_runner=_run_zenity,
        notifier=show_toast,
        log_path=LOG_PATH,
    ):
        self._indicator = None
        self._lock = None
        self._run_item = None
        self._running = False
        self._hud_window = None
        self._config = config or load_config(CONFIG_PATH)
        self._runner = runner
        self._dialog_runner = dialog_runner
        self._notifier = notifier
        self._log_path = log_path
        self._worker_thread = None

    def build_indicator(self):
        indicator = AppIndicator.Indicator.new(
            APP_ID, icon_reference(), AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        if os.path.isdir(ICON_DIR):
            indicator.set_icon_theme_path(ICON_DIR)
        indicator.set_icon_full(icon_reference(), "Docker Janitor")
        menu = build_menu(self.on_run, self.on_about, self.quit_app)
        self._run_item = menu.get_children()[0]
        indicator.set_menu(menu)
        indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self._indicator = indicator
        return indicator

    def on_about(self, *_args):
        return show_about_dialog()

    def on_run(self, *_args):
        """Show HUD popover immediately in scanning state and start preview query."""
        if self._running:
            if self._hud_window:
                self._hud_window.present()
            return False
        if self._hud_window:
            self._hud_window.present()
            return True

        win = JanitorHudWindow(
            preview=None,
            on_clean=self._on_hud_clean,
            on_close=self._on_hud_closed,
            on_exit_app=self.quit_app,
            on_about=self.on_about,
        )
        self._hud_window = win
        win.position_near_tray()
        win.show_all()

        self._running = True
        if self._run_item:
            self._run_item.set_sensitive(False)

        self._worker_thread = threading.Thread(target=self._query_preview, daemon=True)
        self._worker_thread.start()
        return True

    def _query_preview(self):
        try:
            preview = collect_preview(self._config, runner=self._runner)
            GLib.idle_add(self._on_preview_ready, preview)
        except DockerError as exc:
            GLib.idle_add(self._on_preview_error, str(exc))
        except Exception as exc:
            GLib.idle_add(self._on_preview_error, str(exc))

    def _on_preview_ready(self, preview):
        self._running = False
        if self._run_item:
            self._run_item.set_sensitive(True)
        if self._hud_window:
            self._hud_window.set_preview(preview)
        return False

    def _on_preview_error(self, err_msg):
        self._running = False
        if self._run_item:
            self._run_item.set_sensitive(True)
        if self._hud_window:
            self._hud_window.set_error(err_msg)
        self._notifier("Docker Janitor", "Docker error: %s" % err_msg)
        return False

    def _on_hud_clean(self):
        if self._running:
            return
        self._running = True
        if self._run_item:
            self._run_item.set_sensitive(False)
        self._worker_thread = threading.Thread(target=self._execute_prune, daemon=True)
        self._worker_thread.start()

    def _execute_prune(self):
        try:
            cmds = prune_commands(self._config)
            report = run_prune(cmds, runner=self._runner)
            log_report(report, path=self._log_path)
            notify_report(report, notifier=self._notifier)
            GLib.idle_add(self._on_prune_complete, report)
        except DockerError as exc:
            self._notifier("Docker Janitor", "Prune failed: %s" % exc)
            GLib.idle_add(self._on_cycle_complete)
        except Exception as exc:
            self._notifier("Docker Janitor", "Unexpected error: %s" % exc)
            GLib.idle_add(self._on_cycle_complete)

    def _on_prune_complete(self, report):
        if self._hud_window:
            label = (
                "Already clean!"
                if report.reclaimed_bytes == 0
                else "Cleaned %s!" % human_bytes(report.reclaimed_bytes)
            )
            self._hud_window._clean_button.set_label(label)
            GLib.timeout_add(1000, self._close_hud_after_clean)
        else:
            self._on_cycle_complete()
        return False

    def _close_hud_after_clean(self):
        if self._hud_window:
            self._hud_window.destroy()
            self._hud_window = None
        self._on_cycle_complete()
        return False

    def _on_hud_closed(self):
        self._hud_window = None

    def _on_cycle_complete(self):
        self._running = False
        if self._run_item:
            self._run_item.set_sensitive(True)
        return False

    def quit_app(self, *_args):
        if self._hud_window:
            self._hud_window.destroy()
            self._hud_window = None
        self._indicator = None
        Gtk.main_quit()


def print_help():
    print(
        f"{__app_name__} v{__version__}\n\n"
        f"{__description__}\n\n"
        "Usage:\n"
        "  docker-janitor [OPTIONS]\n\n"
        "Options:\n"
        "  -v, --version  Show version and exit\n"
        "  -h, --help     Show this help message and exit\n"
    )


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if "--version" in argv or "-v" in argv:
        print(f"{__app_name__} {__version__}")
        return 0

    if "--help" in argv or "-h" in argv:
        print_help()
        return 0

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
