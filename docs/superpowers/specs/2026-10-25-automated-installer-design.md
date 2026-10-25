# Docker Janitor: Automated One-Line Installer & Distribution Design

## 1. Intent & Problem Statement
Currently, visitors to the Docker Janitor repository face high friction:
- [README.md](README.md) contains no installation guide; prerequisites are only mentioned in [CONTRIBUTING.md](CONTRIBUTING.md).
- Docker Janitor requires native system libraries (`python3-gi`, GTK 3, and Ayatana AppIndicator) that cannot be installed via pure `pip install` without system build tooling or system packages.
- Setting up the system tray indicator, application menu shortcut, and session autostart (`~/.config/autostart/docker-janitor.desktop`) is entirely manual.
- Users need a seamless, one-command installation process that detects missing system dependencies, places the command in `$PATH`, configures desktop integration, and offers clean uninstallation.

## 2. Evaluated Approaches & Decision

### Approach 1: Automated Installer Script (`install.sh` / `uninstall.sh`) [SELECTED]
- **Mechanism**: A portable Bash script in the repository root. Detects the host package manager (`apt`, `dnf`, `pacman`), installs missing system libraries with minimal elevation, places the `docker-janitor` launcher in `~/.local/bin`, installs icons, and registers application menu and autostart `.desktop` entries. Accompanied by a clean `uninstall.sh`.
- **Tradeoffs**: Extremely fast to run, requires no complex build farm or packaging pipeline, supports multi-distro Linux environments, and runs directly from git or a curl one-liner.
- **Decision**: Adopted as the primary distribution method.

### Approach 2: Debian Package (`.deb`) via GitHub Releases
- **Mechanism**: Build `.deb` packages with system dependency declarations for Debian/Ubuntu users.
- **Tradeoffs**: Great for Ubuntu Software GUI users, but distro-specific (excludes Arch and Fedora users) and requires release artifact builds. May be added as a secondary distribution channel later.

### Approach 3: Bundled AppImage
- **Mechanism**: Single executable bundling Python runtime and libraries.
- **Tradeoffs**: Prone to system tray / D-Bus incompatibility with host notification daemons across different Linux desktop environments; high maintenance burden. Dropped.

---

## 3. Specifications & Contracts

### 3.1 `install.sh`
- **Interpreter & Flags**: `#!/usr/bin/env bash` with `set -euo pipefail`.
- **CLI Options**:
  - `--dry-run`: Print installation operations without creating files or running package managers.
  - `--no-autostart`: Install application launcher and icons without configuring `~/.config/autostart/`.
  - `--non-interactive` / `-y`: Accept all defaults and do not prompt interactively.
  - `--prefix=<DIR>`: Specify custom installation prefix (default: `$HOME/.local`).
  - `--help` / `-h`: Display usage synopsis.
- **Dependency Checking**:
  - Validates `python3` (>= 3.8) and `docker` CLI.
  - Tests Python imports for GObject libraries:
    ```bash
    python3 -c "import gi; gi.require_version('Gtk', '3.0'); gi.require_version('AyatanaAppIndicator3', '0.1'); from gi.repository import Gtk, AyatanaAppIndicator3"
    ```
  - If missing, detects package manager and installs required packages (or displays required package names if manager unsupported):
    - **Debian / Ubuntu / Pop!_OS / Mint**: `apt-get install -y python3 python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1`
    - **Fedora / RHEL**: `dnf install -y python3 python3-gobject gtk3 libayatana-appindicator-gtk3`
    - **Arch / Manjaro**: `pacman -S --needed --noconfirm python python-gobject gtk3 libayatana-appindicator`
- **Files Installed**:
  - Executable: `<PREFIX>/bin/docker-janitor` (points to or wraps `docker_janitor.py`).
  - Icon: `<XDG_DATA_HOME>/icons/hicolor/scalable/apps/docker-janitor.svg`.
  - Desktop Entry: `<XDG_DATA_HOME>/applications/docker-janitor.desktop`.
  - Autostart Entry (unless `--no-autostart`): `<XDG_CONFIG_HOME>/autostart/docker-janitor.desktop`.
- **Environment Diagnostics**:
  - Checks if `<PREFIX>/bin` is in `$PATH` and prints export instructions if missing.
  - Runs `update-desktop-database` and `gtk-update-icon-cache` if available (non-fatal).

### 3.2 `uninstall.sh`
- **Interpreter & Flags**: `#!/usr/bin/env bash` with `set -euo pipefail`.
- **CLI Options**:
  - `--dry-run`: Show files to be removed without deleting them.
  - `--purge`: Also remove user configuration (`~/.config/docker-janitor`) and activity logs (`~/.local/state/docker-janitor.log`).
  - `--prefix=<DIR>`: Custom install prefix (default: `$HOME/.local`).
  - `--help` / `-h`: Display usage synopsis.
- **Files Removed**:
  - `<PREFIX>/bin/docker-janitor`
  - `<XDG_DATA_HOME>/applications/docker-janitor.desktop`
  - `<XDG_CONFIG_HOME>/autostart/docker-janitor.desktop`
  - `<XDG_DATA_HOME>/icons/hicolor/scalable/apps/docker-janitor.svg`

### 3.3 Documentation Updates
- **`README.md`**:
  - Add prominent **Installation** section right below Highlights with:
    1. Clone & Run:
       ```bash
       git clone https://github.com/raminmz66/docker-janitor.git
       cd docker-janitor
       ./install.sh
       ```
    2. Quick One-Liner (curl):
       ```bash
       curl -fsSL https://raw.githubusercontent.com/raminmz66/docker-janitor/main/install.sh | bash
       ```
    3. Uninstallation instructions (`./uninstall.sh` and `--purge`).
- **`SPEC.md` & `PLAN.md`**:
  - Record the installer specification and execution milestones.

---

## 4. Verification Plan

1. **Syntax & Static Analysis**:
   - `bash -n install.sh`
   - `bash -n uninstall.sh`
2. **Automated Non-Destructive Unit/Integration Tests (`tests/test_installer.py`)**:
   - Test `--help` and `-h` outputs and zero exit codes.
   - Test `--dry-run` outputs expected actions without touching the filesystem.
   - Test file creation in isolated temporary directories (`--prefix`, `XDG_DATA_HOME`, `XDG_CONFIG_HOME`).
   - Test `--no-autostart` suppresses autostart file creation.
   - Test `uninstall.sh` removes installed files cleanly.
   - Test `uninstall.sh --purge` removes config/log paths.
   - Test idempotency (running `install.sh` repeatedly succeeds without error).
3. **Full Regression Suite**:
   - Run `python3 -m unittest discover -s tests -v`.
   - Run `uvx ruff check .`.
