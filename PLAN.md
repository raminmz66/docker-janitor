# Docker Janitor — Master Plan

Detailed task plans and designs:
- [`docs/superpowers/plans/2026-10-25-project-identity-and-collaboration.md`](docs/superpowers/plans/2026-10-25-project-identity-and-collaboration.md)
- [`docs/superpowers/specs/2026-10-25-project-identity-and-collaboration-design.md`](docs/superpowers/specs/2026-10-25-project-identity-and-collaboration-design.md)

## Active Milestone: Project Identity, Versioning & Collaboration

**Goal:** Establish clear project identity, semantic versioning (`0.1.0`), author attribution (Ramin Maazallahi), MIT licensing, desktop About dialog, and open-source collaboration guidelines.

### Phases
1. **Metadata & CLI Flags**: Define `__version__ = "0.1.0"`, author credits, and handle `--version` and `--help` flags.
2. **Desktop About Dialog**: Native `Gtk.AboutDialog` in Tray Menu & HUD Header.
3. **Open-Source Scaffolding**: `LICENSE`, `pyproject.toml`, `CONTRIBUTING.md`, badges in `README.md`, `STATUS.md`.
4. **Visual UI/UX Verification**: Screenshot capture on active display and layout review.
5. **Merge & Release**: Squash merge to `main`, push to `origin`, delete branch.
