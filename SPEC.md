# Docker Janitor — Specification

## Overview
Docker Janitor is a lightweight desktop system tray indicator for Linux that previews Docker disk space cleanup, asks for confirmation with exact numbers, and prunes only when confirmed.

## Project Identity & Versioning Spec
Full design document: [`docs/superpowers/specs/2026-10-25-project-identity-and-collaboration-design.md`](docs/superpowers/specs/2026-10-25-project-identity-and-collaboration-design.md)

### 1. Versioning
- **Current Version**: `0.1.0`
- Defined canonically in `docker_janitor.__version__` and `pyproject.toml`.
- CLI introspection supported via `--version` and `-v`.
- CLI usage instructions via `--help` and `-h`.

### 2. Authorship & Licensing
- **Author**: Ramin Maazallahi (`r.mazallahi-ext@initiative-crm.com`)
- **License**: MIT (`LICENSE`)
- **Repository**: `https://github.com/raminmz66/docker-janitor`

### 3. Desktop Identity
- **About Dialog**: Native `Gtk.AboutDialog` presenting logo, version, summary, copyright, author credits, license, and repository URL.
- **Entry Points**:
  - System tray menu item: `About Docker Janitor`
  - HUD header bar action button: `ℹ`

### 4. Collaboration & Community
- **`CONTRIBUTING.md`**: Guide for development setup, test execution, commit conventions, and pull request workflows.
- **`pyproject.toml`**: Standard PEP 621 packaging metadata and entrypoint `docker-janitor`.
- **`README.md`**: Badges, maintainer profile, issue reporting, and contribution instructions.

## Automated Installation & Distribution Spec
Full design document: [`docs/superpowers/specs/2026-10-25-automated-installer-design.md`](docs/superpowers/specs/2026-10-25-automated-installer-design.md)

### 1. Zero-Friction Setup
- **`install.sh`**: Portable Bash installer with distro detection (`apt`, `dnf`, `pacman`), automatic dependency checks (`python3-gi`, GTK 3, Ayatana AppIndicator), CLI flag inspection (`--dry-run`, `--no-autostart`, `--prefix`, `--help`), user binary installation (`~/.local/bin/docker-janitor`), scalable SVG icons, and desktop + autostart integration.
- **`uninstall.sh`**: Clean remover for binaries, icons, and desktop launchers with `--dry-run` and optional `--purge` for user config and logs.
- **`README.md`**: Prominent "Quick Installation" instructions right near the top.
