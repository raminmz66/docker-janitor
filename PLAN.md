# Docker Janitor — Implementation Plan

**Goal:** A tray app that previews what Docker cleanup would free, asks before deleting, then reports what it actually reclaimed.

**Architecture:** One Python 3 file (GTK3 + AyatanaAppIndicator3) with a pure "inspection" core that parses Docker CLI output, and a thin shell around it for the menu, dialogs, and toasts. The inspection core is unit-tested against saved CLI output, so tests never touch Docker. **No prune command is ever executed by tests.**

**Tech stack:** Python 3, PyGObject (GTK 3), AyatanaAppIndicator3 0.1, zenity, notify-send, `unittest`. No new packages.

## Global constraints

- No sudo, no new packages, no scheduler or background daemon.
- Never prune volumes or containers; report them only.
- Single instance, enforced with `flock`.
- All user data under `$HOME`; source stays in this repo.
- One destructive step exists in the whole program, and it only runs after the user clicks Continue.

## Files

| Path | Role |
|---|---|
| `docker_janitor.py` | The app: indicator, menu, preview, prune, log |
| `icons/docker-janitor.svg` | Panel icon, hand-authored |
| `tests/` | `unittest` tests + saved Docker output fixtures |
| `~/.config/docker-janitor/config.env` | `IMAGE_MIN_AGE_DAYS=30`, `CACHE_MIN_AGE_HOURS=168` |
| `~/.config/autostart/docker-janitor.desktop` | Starts it at login |
| `README.md` | Thresholds, log location, how to disable |
| `~/.local/state/docker-janitor.log` | Runtime log (created on first run) |

## Review focus

- Docker daemon down → toast, never a traceback.
- Second click on `Run` while running → no second job.
- Output formats that drift between Docker versions → parse defensively, degrade to "estimated".
- Panel widths/themes → icon legible at 22px on light and dark.
- Existing exited containers and volumes → reported, never deleted.

## Tasks

### Task 1 — Shell that shows up

**Files:** create `docker_janitor.py`

**Produces:** `main() -> int`, `class JanitorApp` with `build_indicator()` and `quit_app()`.

Steps:
- [x] Write indicator + lock file + menu (`Run` insensitive, `Exit` active).
- [x] Launch under `DISPLAY=:1`; confirm icon appears and `Exit` returns 0.
- [x] Launch twice; confirm the second instance exits silently.
- [x] Screenshot the panel; confirm the icon renders.

**Done:** `acquire_lock()`, `build_menu()`, `JanitorApp`, `main()` in `docker_janitor.py`; tests in `tests/test_lock.py` (3 passing). Live run showed the icon in the top bar (fallback `edit-clear` until Task 2); second instance exited 0 without a second icon; pressing `Exit` ended the loop with code 0.

### Task 2 — Icon

**Files:** create `icons/docker-janitor.svg`

Steps:
- [x] Draw a bold silhouette (no strokes under 2 units, no text).
- [x] Render at 16/22/48 px.
- [x] Check light and dark backgrounds.

**Done:** `icons/docker-janitor.svg` — docker-blue whale (capsule body, tail fin, spout, white eye), no strokes, no text. Rasterized at 16/22/48 px via librsvg and composited on `#2b2b2b` and `#f5f5f5`; confirmed legible at 22 px, and confirmed in the live panel screenshot on the dark top bar. No unit test applies to an asset; verification is the rendered output.

### Task 3 — Config loader

**Files:** create `tests/test_config.py`; modify `docker_janitor.py`

**Produces:** `load_config(path: str) -> Config` where `Config` has `image_min_age_days: int`, `cache_min_age_hours: int`.

Steps:
- [x] Write failing tests: missing file → defaults; override; malformed value → default kept.
- [x] Run tests; confirm failure.
- [x] Implement `load_config`.
- [x] Run tests; confirm pass.

**Done:** `Config` dataclass + `load_config()` in `docker_janitor.py`; `CONFIG_PATH` resolves to `~/.config/docker-janitor/config.env`. Five tests in `tests/test_config.py`. Comments, blank lines, unknown keys, and malformed values are tolerated; negative values fall back to the default. Real config file created with the two documented keys.

### Task 4 — Inspection core

**Files:** create `tests/test_inspect.py`, `tests/fixtures/*`; modify `docker_janitor.py`

**Produces:** `parse_system_df(text) -> dict`, `unused_images(images, used_ids, now, min_age_days) -> list`, `summarize(preview) -> str`.

Input is captured CLI text, never live Docker.

Steps:
- [x] Save real output as fixtures (`docker system df`, `docker images --format '{{json .}}'`, `docker buildx du --verbose`).
- [x] Write failing tests reproducing measured numbers: images ≈ 23.6 GB reclaimable, cache ≈ 20.8 GB, volumes and 2 exited containers reported as not removable.
- [x] Run tests; confirm failure.
- [x] Implement the three functions.
- [x] Run tests; confirm pass.

**Done:** `parse_size`, `parse_timestamp`, `parse_system_df`, `parse_images`, `parse_used_ids`, `parse_unique_sizes`, `parse_cache_records`, `unused_images`, `dangling_images`, `prunable_cache`, `Preview`, `human_bytes`, `summarize`; 12 tests in `tests/test_inspect.py` over real captures in `tests/fixtures/` (8.7k-line `buildx du --verbose` capture included).

**Two findings from the real data, pinned in tests:**
- Cache rule "reclaimable and not shared" reproduces Docker's own figure exactly: 20.83 GB / 180 entries.
- At the 30-day threshold only 19 unused images qualify (3.56 GB), not the 23.6 GB Docker calls reclaimable — that number counts *all* unused images regardless of age. Most of this machine's images are 10 days to 2 weeks old. With `IMAGE_MIN_AGE_DAYS=0` the preview would show the full 23.6 GB. Live cross-check: janitor 24.4 GB total vs Docker 23.6 GB images + 20.8 GB cache.

### Task 5 — Preview dialog

**Files:** modify `docker_janitor.py`

**Produces:** `collect_preview(config) -> Preview`, `ask_continue(preview) -> bool`.

Steps:
- [ ] Read state read-only (the four commands above).
- [ ] Show zenity `--question` with `Skip`/`Continue` and the breakdown.
- [ ] Verify `Skip` closes with zero Docker mutation.
- [ ] Verify daemon-down shows a toast instead of a dialog.

### Task 6 — Prune and report

**Files:** create `tests/test_prune.py`; modify `docker_janitor.py`

**Produces:** `prune_commands(config) -> list[list[str]]`, `run_prune(cmds, runner) -> Report`.

Steps:
- [ ] Write failing test asserting exact argv: `builder prune -af --filter until=168h`, `image prune -f`, `image prune -af --filter until=720h`, and that no `volume`/`container` prune appears.
- [ ] Implement command construction behind an injectable runner.
- [ ] Verify before/after `df` delta → toast → log append.
- [ ] Run tests; confirm pass. Do not execute real prunes.

### Task 7 — Wire it up

**Files:** modify `docker_janitor.py`

Steps:
- [ ] `Run` starts a worker thread, disables itself, marshals updates with `GLib.idle_add`.
- [ ] Verify double-click `Run` starts one job.
- [ ] Verify a forced failure logs and toasts without killing the indicator.

### Task 8 — Autostart and README

**Files:** create `~/.config/autostart/docker-janitor.desktop`, `README.md`

Steps:
- [ ] Write the desktop entry pointing at `/usr/bin/python3 /home/ramin/projects/docker-janitor/docker_janitor.py`.
- [ ] Validate it (`desktop-file-validate` if present).
- [ ] Document thresholds, log path, disable steps.

### Pending decision — log rotation

Not in scope until answered: `max-size=10m, max-file=3` in `/etc/docker/daemon.json` requires a `dockerd` restart that bounces all 10 `devenv_*` containers.

## Verification before handover

- [ ] `python3 -m py_compile docker_janitor.py`
- [ ] `python3 -m unittest discover -s tests -v` all green
- [ ] Live launch with screenshot of the icon
- [ ] `docker system df` identical before and after the whole session (no prune ran)
