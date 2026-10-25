# Docker Janitor — Master Plan

Detailed task plans and designs:
- [`docs/superpowers/plans/2026-10-25-automated-installer.md`](docs/superpowers/plans/2026-10-25-automated-installer.md)
- [`docs/superpowers/specs/2026-10-25-automated-installer-design.md`](docs/superpowers/specs/2026-10-25-automated-installer-design.md)
- [`docs/superpowers/plans/2026-10-25-project-identity-and-collaboration.md`](docs/superpowers/plans/2026-10-25-project-identity-and-collaboration.md)
- [`docs/superpowers/specs/2026-10-25-project-identity-and-collaboration-design.md`](docs/superpowers/specs/2026-10-25-project-identity-and-collaboration-design.md)

## Active Milestone: Automated Installation & Distribution

**Goal:** Provide zero-friction, one-command installation of Docker Janitor via `install.sh`, `uninstall.sh`, and documentation in `README.md`.

### Phases
1. **Automated Installer Script (`install.sh`)**: Dependency checks, distro package manager detection (`apt`, `dnf`, `pacman`), CLI flags (`--dry-run`, `--no-autostart`, `--prefix`, `--help`), and desktop integration.
2. **Uninstaller Script (`uninstall.sh`)**: Clean removal of binaries, desktop entries, icons, and optional config purge (`--purge`).
3. **Automated Installer Tests**: Non-destructive integration tests in `tests/test_installer.py`.
4. **Documentation**: Quick installation instructions in `README.md` and `CONTRIBUTING.md`.
5. **Merge & Release**: Full verification, squash merge to `main`, push to `origin`, delete branch.
