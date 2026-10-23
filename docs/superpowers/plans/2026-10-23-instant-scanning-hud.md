# Instant Scanning HUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide 0ms instant feedback when clicking "Run" by opening the Popover HUD immediately in an active scanning state with a spinner, updating in-place once Docker CLI inspection finishes.

**Architecture:** Extend `JanitorHudWindow` to support dynamic state transitions (`scanning` -> `ready` or `error`). Update `JanitorApp.on_run()` to open the window synchronously before dispatching the background worker thread.

**Tech Stack:** Python 3, GTK 3 (PyGObject), Gdk 3, GLib, `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-23-instant-scanning-hud-design.md`

## Global Constraints
- Pure Python 3 and GTK 3 without new external dependencies.
- Zero-millisecond delay on user click (window must show immediately).
- Strictly on-demand execution (no continuous polling daemons).
- Preserve safety invariants (never prune containers or volumes).

## Review Focus
1. **Window Size Stability**: The window dimensions must remain constant between scanning state and loaded state so the UI does not visually jump or resize.
2. **Double Click Prevention**: If the user clicks "Run" while already scanning or open, `self._hud_window.present()` is called without restarting queries.
3. **Dismissal During Scan**: If the user hits `Escape` while scanning is still in progress, the window closes gracefully and the background worker discards its result on completion.
4. **Daemon Down During Scan**: If `collect_preview` raises `DockerError`, the window transitions to an inline error state with a "Close" button without crashing.
5. **Clean Button Safety**: The clean button remains strictly disabled while scanning.

---

### Task 1: Scanning & Dynamic In-Place Updates in `JanitorHudWindow`

**Files:**
- Modify: `docker_janitor.py`
- Modify: `tests/test_hud.py`

**Interfaces:**
- Produces: `JanitorHudWindow(preview=None, ...)`, `JanitorHudWindow.set_preview(preview: Preview)`, `JanitorHudWindow.set_error(message: str)`
- Consumes: `Preview`, `build_segmented_bar()`

- [x] **Step 1: Write failing tests for scanning state, `set_preview()`, and `set_error()`**
- [x] **Step 2: Run tests to verify failure**
- [x] **Step 3: Implement scanning state, `set_preview()`, and `set_error()` in `docker_janitor.py`**
- [x] **Step 4: Run tests to verify pass**
- [x] **Step 5: Commit `feat(hud): support instant scanning state and in-place preview population`**

---

### Task 2: Synchronous Window Launch & Thread Wiring in `JanitorApp`

**Files:**
- Modify: `docker_janitor.py`
- Modify: `tests/test_wire.py`

**Interfaces:**
- Produces: `JanitorApp.on_run()` opening HUD synchronously; `_on_preview_ready()`, `_on_preview_error()`
- Consumes: `JanitorHudWindow`, `collect_preview()`, `GLib.idle_add()`

- [x] **Step 1: Write failing tests asserting HUD opens synchronously and updates on query completion**
- [x] **Step 2: Run tests to verify failure**
- [x] **Step 3: Wire instant HUD launch and asynchronous data binding in `docker_janitor.py`**
- [x] **Step 4: Run tests to verify pass**
- [x] **Step 5: Commit `feat(app): open HUD window immediately upon click with in-place data binding`**

---

### Task 3: Verification, Live Service Restart & Visual Validation

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-10-23-instant-scanning-hud.md`

- [x] **Step 1: Update documentation and mark plan steps complete**
- [x] **Step 2: Run full test suite with broadway across all test files**
- [x] **Step 3: Restart user desktop service and capture live screenshot of scanning state**
- [x] **Step 4: Commit `docs: update documentation and record instant HUD verification`**
