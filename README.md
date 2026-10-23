# Docker Janitor

A lightweight desktop system tray indicator for Linux that previews Docker disk space cleanup, asks for confirmation with exact numbers, and prunes only when you choose to proceed.

![Whale Icon](icons/docker-janitor.svg)

## Highlights

- **Safety First**: Never touches or prunes volumes or containers (active or stopped). Only unreferenced images and build cache entries older than configured age thresholds are ever prunable.
- **Preview Before Deleting**: Clicking **Run** calculates an exact preview of reclaimable space and presents a confirmation dialog. Closing or clicking **Skip** aborts without touching Docker.
- **Single Instance**: Enforced via file lock (`$XDG_RUNTIME_DIR/docker-janitor.lock`). Launching again exits cleanly without duplicate tray icons.
- **No Background Daemon or Sudo**: Runs strictly as the current user, using your existing Docker CLI permissions and standard system desktop tools (`zenity`, `notify-send`, PyGObject).

## Configuration

Configuration is stored in `~/.config/docker-janitor/config.env`:

```env
# Minimum age (in days) for unused images to qualify for cleanup
IMAGE_MIN_AGE_DAYS=30

# Minimum age (in hours) for build cache entries to qualify for cleanup (168h = 7 days)
CACHE_MIN_AGE_HOURS=168
```

If the file does not exist, defaults (`30` days and `168` hours) are used automatically. Comments and blank lines are ignored.

## Activity Log

Each successful prune operation appends a record to:

```
~/.local/state/docker-janitor.log
```

Log entry format:
```
2026-10-23T21:30:00+03:30 reclaimed 24.4 GB (before: 46.0 GB, after: 21.6 GB)
```

## Autostart & Disabling

Docker Janitor starts automatically on login via:

```
~/.config/autostart/docker-janitor.desktop
```

### To disable autostart:
Remove the desktop file:
```bash
rm ~/.config/autostart/docker-janitor.desktop
```
Or set `X-GNOME-Autostart-enabled=false` inside the desktop file.

### To exit:
Click the whale icon in the panel and select **Exit**.

## Running Tests

Run the full test suite using Python's built-in `unittest`:

```bash
python3 -m unittest discover -s tests -v
```

All inspection and prune tests execute against saved CLI fixtures; tests never touch live Docker daemons or issue prune commands.
