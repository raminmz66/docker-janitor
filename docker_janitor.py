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
from typing import List

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")

from gi.repository import AyatanaAppIndicator3 as AppIndicator  # noqa: E402
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

APP_ID = "docker-janitor"
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


def build_menu(on_run, on_exit):
    """Menu with exactly two entries: Run and Exit."""
    menu = Gtk.Menu()

    run_item = Gtk.MenuItem(label="Run")
    run_item.set_sensitive(True)
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
.janitor-hud {
    background-color: @theme_base_color;
    color: @theme_text_color;
    border: 1px solid alpha(@theme_text_color, 0.2);
    border-radius: 12px;
}
.janitor-hero-number {
    font-size: 26px;
    font-weight: 700;
    color: #0db7ed;
}
.janitor-segmented-bar {
    border-radius: 5px;
    background-color: alpha(@theme_text_color, 0.1);
    min-height: 10px;
}
.bar-segment-cache {
    background-color: #0db7ed;
}
.bar-segment-images {
    background-color: #ff9f0a;
}
.bar-segment-kept {
    background-color: alpha(@theme_text_color, 0.25);
}
.janitor-badge {
    background-color: rgba(52, 199, 89, 0.15);
    border-radius: 6px;
    padding: 6px 10px;
    color: #2e7d32;
    font-size: 11px;
}
.janitor-btn-primary {
    background-color: #0db7ed;
    color: white;
    font-weight: 600;
    border-radius: 6px;
    padding: 8px 16px;
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

    for key, class_name in (
        ("cache", "bar-segment-cache"),
        ("images", "bar-segment-images"),
        ("kept", "bar-segment-kept"),
    ):
        seg = Gtk.Box()
        seg.get_style_context().add_class(class_name)
        box.pack_start(seg, True, True, 0)
        seg.set_size_request(max(4, int(300 * props[key])), 10)

    return box


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
    """Short image IDs currently referenced by any container (running or not)."""
    used = set()
    for raw in (text or "").splitlines():
        raw = raw.strip()
        if raw.startswith("sha256:"):
            used.add(raw[7:19])
        elif raw:
            used.add(raw[:12])
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

    def flush():
        if current.get("created") is not None and current.get("size") is not None:
            records.append(
                CacheRecord(
                    id=current.get("id", ""),
                    created=current["created"],
                    reclaimable=current.get("reclaimable", False),
                    shared=current.get("shared", False),
                    size=current["size"],
                )
            )
            current.clear()

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            flush()
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
        elif label == "Reclaimable":
            current["reclaimable"] = value == "true"
        elif label == "Shared":
            current["shared"] = value == "true"
        elif label == "Size":
            current["size"] = parse_size(value)
    flush()
    return records


def unused_images(images, used_ids, now, min_age_days):
    """Tagged images no container references and older than the threshold."""
    cutoff = now - timedelta(days=min_age_days)
    return [
        image
        for image in images
        if image.id not in used_ids
        and not (image.repository == "<none>" and image.tag == "<none>")
        and image.created < cutoff
    ]


def dangling_images(images):
    return [
        image
        for image in images
        if image.repository == "<none>" and image.tag == "<none>"
    ]


def prunable_cache(records, now, min_age_hours):
    """Only private, reclaimable records: shared ones are still needed by images."""
    cutoff = now - timedelta(hours=min_age_hours)
    return [
        record
        for record in records
        if record.reclaimable and not record.shared and record.created < cutoff
    ]


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
            runner("container", "inspect", "--format", "{{.Image}}", *container_ids)
        )
    unique = parse_unique_sizes(runner("system", "df", "-v"))
    if now is None:
        now = datetime.now().astimezone()

    old_images = unused_images(images, used, now, config.image_min_age_days)
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
        menu = build_menu(self.on_run, self.quit_app)
        self._run_item = menu.get_children()[0]
        indicator.set_menu(menu)
        indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self._indicator = indicator
        return indicator

    def on_run(self, *_args):
        """Start preview and cleanup in a background worker."""
        if self._running:
            return False
        self._running = True
        if self._run_item:
            self._run_item.set_sensitive(False)

        self._worker_thread = threading.Thread(target=self._run_cycle, daemon=True)
        self._worker_thread.start()
        return True

    def _run_cycle(self):
        try:
            try:
                preview = collect_preview(self._config, runner=self._runner)
            except DockerError as exc:
                self._notifier("Docker Janitor", "Docker error: %s" % exc)
                return

            if preview.empty:
                self._notifier("Docker Janitor", "No Docker data to clean up.")
                return

            confirmed = ask_continue(preview, runner=self._dialog_runner)
            if not confirmed:
                return

            try:
                cmds = prune_commands(self._config)
                report = run_prune(cmds, runner=self._runner)
                log_report(report, path=self._log_path)
                notify_report(report, notifier=self._notifier)
            except DockerError as exc:
                self._notifier("Docker Janitor", "Prune failed: %s" % exc)
        except Exception as exc:
            try:
                self._notifier("Docker Janitor", "Unexpected error: %s" % exc)
            except Exception:
                pass
        finally:
            GLib.idle_add(self._on_cycle_complete)

    def _on_cycle_complete(self):
        self._running = False
        if self._run_item:
            self._run_item.set_sensitive(True)
        return False

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
