# Docker Janitor — Project Status

## Current Milestone: v0.1.0 (Identity & Collaboration)

**Status:** Completed & Ready for Release

### Completed Features & Invariants
- [x] **Safe Pruning Core**: Never touches volumes or active/stopped containers. Age thresholds for unused images and build cache.
- [x] **Popover HUD**: Instant scanning state with animated spinner, dynamic in-place data binding, segmented color bar, and safety badges.
- [x] **Desktop Identity**: Native `Gtk.AboutDialog` accessible via tray indicator menu and HUD header bar.
- [x] **CLI Flag Introspection**: `--version`, `-v`, `--help`, `-h` support.
- [x] **Single-Instance Enforcement**: Strict `$XDG_RUNTIME_DIR/docker-janitor.lock` file locking.
- [x] **Open-Source Infrastructure**: `LICENSE` (MIT), `pyproject.toml` (PEP 621), `CONTRIBUTING.md`, `README.md` badges, and author attribution.
- [x] **Non-destructive Test Suite**: 62 unit tests verifying offline execution against saved fixtures.

### Project Links
- **Repository**: [https://github.com/raminmz66/docker-janitor](https://github.com/raminmz66/docker-janitor)
- **Author**: Ramin Maazallahi (`r.mazallahi-ext@initiative-crm.com`)
- **License**: MIT
