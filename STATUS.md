# Docker Janitor — Project Status

## Current Milestone: v0.1.0 (Automated Installation & Identity)

**Status:** Completed & Ready for Release

### Completed Features & Invariants
- [x] **Automated Installer & Uninstaller**: Portable user-space `./install.sh` and `./uninstall.sh` supporting `--dry-run`, `--no-autostart`, `--prefix`, `--purge`, and multi-distro dependency resolution (`apt`, `dnf`, `pacman`).
- [x] **Safe Pruning Core**: Never touches volumes or active/stopped containers. Age thresholds for unused images and build cache.
- [x] **Image Preview & Prune Alignment**: Queries Docker's `until` filter during preview to guarantee 100% consistency between detected space and actual prune output, respecting local tag/pull activity.
- [x] **Popover HUD**: Instant scanning state with animated spinner, dynamic in-place data binding, segmented color bar, and safety badges.
- [x] **Desktop Identity**: Native `Gtk.AboutDialog` accessible via tray indicator menu and HUD header bar.
- [x] **CLI Flag Introspection**: `--version`, `-v`, `--help`, `-h` support.
- [x] **Single-Instance Enforcement**: Strict `$XDG_RUNTIME_DIR/docker-janitor.lock` file locking.
- [x] **Open-Source Infrastructure**: `LICENSE` (MIT), `pyproject.toml` (PEP 621), `CONTRIBUTING.md`, `README.md` badges, and author attribution.
- [x] **Non-destructive Test Suite**: 75 unit tests verifying offline execution against saved fixtures, mock runners, and installer flows.

### Project Links
- **Repository**: [https://github.com/raminmz66/docker-janitor](https://github.com/raminmz66/docker-janitor)
- **Author**: Ramin Maazallahi (`r.mazallahi-ext@initiative-crm.com`)
- **License**: MIT
