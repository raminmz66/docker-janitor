# Contributing to Docker Janitor

Thank you for your interest in contributing to **Docker Janitor**! We welcome bug reports, improvements, documentation updates, and feature discussions.

---

## 1. Guiding Philosophy & Invariants

Docker Janitor is designed around strict safety guarantees for developers' local environments. Any contribution must respect these invariants:

1. **Safety First**:
   - Never touch or prune containers (running or stopped) or volumes.
   - Only unused, unreferenced images and old build cache entries exceeding configured thresholds are eligible for cleanup.
2. **Strict User Consent**:
   - No automatic or background deletions. The app previews reclaimable space and only executes cleanup when the user explicitly clicks the cleanup button.
3. **No Root / Sudo or Background Daemons**:
   - Runs strictly within standard user permissions using the Docker CLI and standard desktop session libraries (GTK 3, AyatanaAppIndicator).
4. **Hermetic, Non-Destructive Tests**:
   - Unit tests run against saved CLI output fixtures and mock runners. **Tests must never connect to live Docker daemons or issue destructive prune commands.**

---

## 2. Getting Started

### Prerequisites
- Linux OS with X11 or Wayland
- Python 3.8+
- PyGObject (`python3-gi`)
- GTK 3 (`libgtk-3-0` or `gtk3`)
- Ayatana AppIndicator (`gir1.2-ayatanaappindicator3-0.1` or `libayatana-appindicator3`)
- Docker CLI

On Debian/Ubuntu-based systems:
```bash
sudo apt-get install python3 python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
```

### Clone the Repository
```bash
git clone https://github.com/raminmz66/docker-janitor.git
cd docker-janitor
```

### Running Locally
```bash
# Launch the desktop indicator
python3 docker_janitor.py

# Or inspect CLI flags
python3 docker_janitor.py --version
python3 docker_janitor.py --help
```

---

## 3. Running Tests

Run the complete test suite using Python's standard `unittest`:

```bash
python3 -m unittest discover -s tests -v
```

All 60+ tests should pass quickly and completely offline without requiring Docker to be running.

### Code Style & Linting
We follow PEP 8 and modern Python conventions. You can verify code formatting and linting with Ruff:

```bash
uvx ruff check .
```

---

## 4. Development Workflow

1. **Work on a Dedicated Feature Branch**:
   ```bash
   git checkout -b feat/your-feature-name
   # or
   git checkout -b fix/issue-description
   ```

2. **Commit Early and Often**:
   We follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat: ...` for new features or capabilities
   - `fix: ...` for bug fixes
   - `docs: ...` for documentation changes
   - `test: ...` for adding or updating tests
   - `refactor: ...` for code refactoring without behavior changes

3. **Verify Before Pushing**:
   Ensure all tests pass and your branch is clean:
   ```bash
   python3 -m unittest discover -s tests -v
   ```

4. **Submit a Pull Request**:
   - Open a PR against `main` on GitHub.
   - Describe the problem your change solves and include test output.
   - Pull requests are merged using **squash and merge** to keep git history clean.

---

## 5. Reporting Issues & Questions

If you encounter a bug or have a suggestion:
- Check existing issues in the [Issue Tracker](https://github.com/raminmz66/docker-janitor/issues).
- If it's a new issue, open a report including your Linux distribution, desktop environment, Docker version, and steps to reproduce.
