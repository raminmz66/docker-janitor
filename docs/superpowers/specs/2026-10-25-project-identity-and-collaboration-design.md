# Docker Janitor: Project Identity, Versioning & Collaboration Design

## 1. Intent & Problem Statement
Docker Janitor is currently anonymous. Users and developers running or inspecting the code have no way of knowing:
- What version is running (`__version__` and `--version` are absent).
- Who created and maintains the application (no credits or author attribution).
- What license governs the codebase (no `LICENSE` file).
- How the app presents itself on desktop (the tray menu only contains "Run" and "Exit", with no "About" dialog).
- How developers can contribute (no `CONTRIBUTING.md`, no packaging metadata in `pyproject.toml`, no repository links in `README.md`).

## 2. Goals & Constraints
- **Canonical Versioning**: Establish Semantic Versioning (`0.1.0`) as the single source of truth across code, CLI, packaging, and documentation.
- **Native GTK Desktop Identity**: Implement a native `Gtk.AboutDialog` displaying the whale icon, version `0.1.0`, description, copyright, author credits, MIT license, and GitHub repository link.
- **Dual Access Points**: Accessible both from the tray indicator menu ("About Docker Janitor") and an info icon in the Popover HUD header.
- **Fast CLI Introspection**: Support `--version` (`-v`) and `--help` (`-h`) that output immediately to stdout without requiring an X11 display, GTK init, or file locking.
- **Complete Open-Source Scaffolding**: Add `LICENSE` (MIT), `pyproject.toml` (PEP 621), `CONTRIBUTING.md` (developer onboarding & PR workflows), and updated `README.md` with badges and maintainer details.
- **Visual Verification**: Capture and inspect screenshots of the About Dialog and HUD UI on active display.
- **Zero Breakage**: Maintain 100% test coverage and preserve all safety invariants (never delete containers/volumes, tests never run live Docker prune).

## 3. Architecture & Interfaces

### 3.1 Metadata Constants (`docker_janitor.py`)
```python
__version__ = "0.1.0"
__app_name__ = "Docker Janitor"
__author__ = "Ramin Maazallahi"
__email__ = "r.mazallahi-ext@initiative-crm.com"
__license__ = "MIT"
__website__ = "https://github.com/raminmz66/docker-janitor"
__description__ = "A lightweight Linux desktop indicator for previewing and safely cleaning Docker disk space."
```

### 3.2 CLI Argument Handling
In `main(argv=None)`:
- If `--version` or `-v` in `argv`: prints `f"{__app_name__} {__version__}"` and exits 0.
- If `--help` or `-h` in `argv`: prints command description, flags, and exits 0.
- Otherwise, proceeds to lock acquisition and GTK event loop.

### 3.3 About Dialog (`show_about_dialog(parent=None)`)
- Creates a `Gtk.AboutDialog`.
- Sets `program_name`, `version`, `comments`, `copyright`, `website`, `website_label="GitHub Repository"`, `authors`, and `license_type=Gtk.License.MIT_X11`.
- Loads `icons/docker-janitor.svg` as pixbuf (96x96) for the dialog logo.
- Connects `"response"` signal to close/destroy the dialog.
- Connects tray indicator menu item `"About Docker Janitor"` and HUD header info button to this helper.

### 3.4 Menu Structure
`build_menu(on_run, on_about, on_exit)`:
1. `Gtk.MenuItem("Run")`
2. `Gtk.MenuItem("About Docker Janitor")`
3. `Gtk.SeparatorMenuItem()`
4. `Gtk.MenuItem("Exit")`

### 3.5 HUD Header Integration
In `JanitorHudWindow.__init__`:
- Add an info button (`ℹ`) to the right side of the header next to the close button (`✕`), styled cleanly, opening `show_about_dialog(parent=self)`.

### 3.6 Repository Files
- `LICENSE`: MIT License (2026 Ramin Maazallahi).
- `pyproject.toml`: Modern packaging metadata, build system, project URLs, and CLI entry point `docker-janitor = "docker_janitor:main"`.
- `CONTRIBUTING.md`: Contributing guide covering setup, test suite execution, Git branch/commit conventions, and PR guidelines.
- `README.md`: Badges, author attribution, contributing guide pointer, license details, and GitHub links.
- `STATUS.md`: Current project status, milestones, and release readiness.

## 4. Verification Plan
1. **Automated Unit Tests**:
   - `tests/test_identity.py`: Tests `--version`, `-v`, `--help`, `-h`, metadata constants, and `show_about_dialog()` properties.
   - `tests/test_lock.py`: Updates menu item tests to check `["Run", "About Docker Janitor", "Exit"]` and separator.
   - `tests/test_hud.py`: Verifies HUD header info button presence and callback.
2. **Visual Verification**:
   - Run screenshot capture script on `DISPLAY=:1`.
   - Save screenshots to `docs/screenshots/about-dialog.png` and `docs/screenshots/hud-window.png`.
   - Review image geometry, fonts, contrast, and alignment.
3. **Full Suite**:
   - Run `python3 -m unittest discover -s tests -v` (100% passing).
   - Run `uvx ruff check .` and formatting checks.
