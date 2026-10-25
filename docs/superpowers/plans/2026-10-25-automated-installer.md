# Automated Installer & Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a seamless, automated installation experience for Docker Janitor via an `install.sh` script, clean `uninstall.sh`, and prominent instructions in `README.md`.

**Architecture:**
- Standalone portable Bash scripts (`install.sh`, `uninstall.sh`) running without mandatory root permissions.
- Automatic detection of missing system libraries (`python3-gi`, GTK 3, Ayatana AppIndicator) with package manager support (`apt`, `dnf`, `pacman`).
- User-space desktop integration: `~/.local/bin/docker-janitor`, scalable SVG icon, application launcher in `~/.local/share/applications`, and optional autostart in `~/.config/autostart`.
- Full CLI flag support: `--dry-run`, `--no-autostart`, `--non-interactive` (`-y`), `--purge`, `--prefix`, `--help`.
- Non-destructive automated Python tests verifying flags, paths, permissions, and clean uninstall.

**Spec:** `docs/superpowers/specs/2026-10-25-automated-installer-design.md`

## Global Constraints
- Python 3.8+ compatibility.
- Shell scripts use standard `#!/usr/bin/env bash` with `set -euo pipefail`.
- No forced sudo/root; runs in user-space (`$HOME/.local`). Sudo is only invoked if missing system packages require installation.
- Tests must never connect to live Docker daemons or mutate user's actual home files outside temporary test directories.

## Review Focus
- Dry run: verify `--dry-run` performs zero filesystem modifications.
- Path resolution: ensure scripts work correctly when executed from any working directory or via pipe (`curl ... | bash`).
- Prefix overrides: verify `--prefix` and XDG environment variables (`XDG_DATA_HOME`, `XDG_CONFIG_HOME`) are respected.
- Clean removal: verify `uninstall.sh` removes all installed files and `--purge` removes config/logs.
- Idempotency: verify running `install.sh` twice produces no duplicate files or errors.

---

## Tasks

### Task 1: Automated Installer Script (`install.sh`)

**Files:**
- Create: `install.sh`

- [ ] **Step 1: Create `install.sh` with argument parsing (`--dry-run`, `--no-autostart`, `-y`, `--prefix`, `--help`)**
- [ ] **Step 2: Add dependency checks for `python3`, `docker`, and GObject libraries (`python3-gi`, `Gtk 3.0`, `AyatanaAppIndicator3 0.1`)**
- [ ] **Step 3: Implement package manager installation commands for `apt-get`, `dnf`, and `pacman`**
- [ ] **Step 4: Implement file installation: binary wrapper/symlink, SVG icons, desktop application launcher, and autostart desktop entry**
- [ ] **Step 5: Make `install.sh` executable and verify bash syntax with `bash -n install.sh`**

---

### Task 2: Uninstaller Script (`uninstall.sh`)

**Files:**
- Create: `uninstall.sh`

- [ ] **Step 1: Create `uninstall.sh` with argument parsing (`--dry-run`, `--purge`, `--prefix`, `--help`)**
- [ ] **Step 2: Implement removal of binary, application desktop entry, autostart desktop entry, and icons**
- [ ] **Step 3: Implement `--purge` removal of config (`~/.config/docker-janitor`) and logs (`~/.local/state/docker-janitor.log`)**
- [ ] **Step 4: Make `uninstall.sh` executable and verify bash syntax with `bash -n uninstall.sh`**

---

### Task 3: Automated Installer Test Suite

**Files:**
- Create: `tests/test_installer.py`

- [ ] **Step 1: Write test cases in `tests/test_installer.py` for `--help` on `install.sh` and `uninstall.sh`**
- [ ] **Step 2: Write test cases for `--dry-run` verifying no files are written**
- [ ] **Step 3: Write test cases for installation into temporary directory prefix verifying file creation, desktop contents, and permissions**
- [ ] **Step 4: Write test cases for `--no-autostart` verifying autostart entry is omitted**
- [ ] **Step 5: Write test cases for `uninstall.sh` verifying clean removal and `--purge`**
- [ ] **Step 6: Write test cases verifying idempotency of `install.sh`**
- [ ] **Step 7: Run tests via `python3 -m unittest tests/test_installer.py -v` to verify they pass**

---

### Task 4: Documentation Updates

**Files:**
- Modify: `README.md`
- Modify: `CONTRIBUTING.md`
- Modify: `STATUS.md`

- [ ] **Step 1: Add prominent Quick Installation section to `README.md` with git clone and one-line curl instructions**
- [ ] **Step 2: Document uninstallation and flag options in `README.md`**
- [ ] **Step 3: Update `CONTRIBUTING.md` and `STATUS.md` to reflect automated installer availability**

---

### Task 5: Full Verification, Squash Merge, Push & Cleanup

- [ ] **Step 1: Run complete test suite (`python3 -m unittest discover -s tests -v`)**
- [ ] **Step 2: Run linter checks (`uvx ruff check .`)**
- [ ] **Step 3: Switch to `main`, squash merge `feat/automated-installer`**
- [ ] **Step 4: Push `main` to `origin/main`**
- [ ] **Step 5: Delete local branch `feat/automated-installer`**
