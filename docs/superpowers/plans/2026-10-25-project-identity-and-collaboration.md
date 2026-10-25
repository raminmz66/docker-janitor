# Project Identity, Versioning & Collaboration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish clear project identity, semantic versioning (`0.1.0`), author attribution (Ramin Maazallahi), MIT licensing, desktop About dialog, and open-source collaboration guidelines.

**Architecture:**
- Single-source metadata in `docker_janitor.py` and `pyproject.toml`.
- CLI `--version` and `--help` flags handled before GUI / lock acquisition.
- Native `Gtk.AboutDialog` accessible from the AppIndicator tray menu and HUD header bar.
- Open-source files: `LICENSE`, `pyproject.toml`, `CONTRIBUTING.md`, `README.md`, `STATUS.md`.

**Spec:** `docs/superpowers/specs/2026-10-25-project-identity-and-collaboration-design.md`

## Tasks

### Task 1: Metadata, Versioning & CLI Flags

**Files:**
- Modify: `docker_janitor.py`
- Create: `tests/test_identity.py`

- [x] **Step 1: Write unit tests in `tests/test_identity.py` for metadata constants, `--version`, and `--help`**
- [x] **Step 2: Run tests to verify failure**
- [x] **Step 3: Implement metadata constants and `parse_cli_args()` / `main(argv)` handling in `docker_janitor.py`**
- [x] **Step 4: Run tests to verify pass**
- [x] **Step 5: Commit `feat: add semantic versioning and CLI flags`**

---

### Task 2: Desktop About Dialog in Tray Menu & HUD Header

**Files:**
- Modify: `docker_janitor.py`
- Modify: `tests/test_lock.py`
- Modify: `tests/test_hud.py`
- Modify: `tests/test_identity.py`

- [x] **Step 1: Write unit tests for `show_about_dialog()`, tray menu `About Docker Janitor` item, and HUD info button**
- [x] **Step 2: Run tests to verify failure**
- [x] **Step 3: Implement `show_about_dialog()`, update `build_menu()`, and add header info button in `JanitorHudWindow`**
- [x] **Step 4: Run tests to verify pass**
- [x] **Step 5: Commit `feat(ui): add native GTK About dialog to tray menu and HUD header`**

---

### Task 3: Open-Source Collaboration Scaffolding

**Files:**
- Create: `LICENSE`
- Create: `pyproject.toml`
- Create: `CONTRIBUTING.md`
- Create: `STATUS.md`
- Modify: `README.md`

- [x] **Step 1: Create `LICENSE` with MIT terms and copyright notice**
- [x] **Step 2: Create `pyproject.toml` with PEP 621 packaging metadata, scripts, and URLs**
- [x] **Step 3: Create `CONTRIBUTING.md` with guidelines, test instructions, and PR workflows**
- [x] **Step 4: Update `README.md` with project badges, author profile, collaboration links, and license info**
- [x] **Step 5: Create `STATUS.md` recording current release milestone and roadmap**
- [x] **Step 6: Commit `docs: add open-source licensing, packaging, and contributing guidelines`**

---

### Task 4: UI/UX Screenshot Verification & Visual Review

**Files:**
- Create: `scripts/capture_screenshots.py`
- Output: `docs/screenshots/about-dialog.png`, `docs/screenshots/hud-window.png`

- [x] **Step 1: Write screenshot capture script using GTK window display and `/usr/bin/import`**
- [x] **Step 2: Execute screenshot capture on active X11 display (`DISPLAY=:1`)**
- [x] **Step 3: Inspect captured images and review UI/UX layout, fonts, icon scaling, and alignment**
- [x] **Step 4: Commit `test(ui): add visual review screenshots for About dialog and HUD`**

---

### Task 5: Final Verification, Squash Merge, Push & Cleanup

- [x] **Step 1: Run full unit test suite (`python3 -m unittest discover -s tests -v`)**
- [x] **Step 2: Run code quality checks (`uvx ruff check .`)**
- [ ] **Step 3: Switch to `main`, squash merge the feature branch**
- [ ] **Step 4: Push to `origin/main`**
- [ ] **Step 5: Delete feature branch `feat/project-identity-and-collaboration`**
- [ ] **Step 6: Notify user of complete task execution**
