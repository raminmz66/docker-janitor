# Native GTK Popover HUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Zenity confirmation dialog with a modern, native GTK3 Popover HUD anchored directly beneath the top panel indicator.

**Architecture:** Implement a frameless `Gtk.Window` with custom GTK CSS, a segmented color-coded storage bar widget, and responsive action buttons. It anchors near the top-right tray icon, auto-dismisses on blur or `Escape`, and provides live feedback during cleanup.

**Tech Stack:** Python 3, PyGObject (GTK 3, Gdk 3, AyatanaAppIndicator3 0.1), GLib, `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-23-popover-hud-design.md`

## Global Constraints

- Pure Python 3 and GTK 3 without external GUI libraries or npm packages.
- Never prune volumes or containers; strictly preserve existing safety invariants.
- Auto-dismiss on click outside (`focus-out-event`) or `Escape` key without locking input focus.
- Safe headless execution for unit tests (broadway or mock environments).

## Review Focus

1. **Zero Reclaimable Space**: When `preview.empty` is true (0 B freeable), the HUD cleanly displays "0 B" and disables the clean button with a friendly message.
2. **Clicking Outside to Dismiss**: Clicking any desktop window outside the HUD emits `focus-out-event` and closes the HUD without triggering prune.
3. **Double Click Clean Action**: Rapidly clicking the "Free Now" button triggers only one prune job and sets the button to busy.
4. **Display Geometry Edge Cases**: If screen width/height is constrained, positioning code clamps coordinates within monitor boundaries.
5. **Escape Key Dismissal**: Pressing `Escape` key closes the HUD immediately with 0 Docker mutation.

---

### Task 1: Segmented Storage Bar & CSS Theme

**Files:**
- Modify: `docker_janitor.py`
- Create: `tests/test_hud.py`

**Interfaces:**
- Produces: `calculate_storage_proportions(cache_bytes: int, image_bytes: int, kept_bytes: int) -> dict[str, float]`, `build_segmented_bar(cache_bytes: int, image_bytes: int, kept_bytes: int) -> Gtk.Box`
- Consumes: `Preview` dataclass, `human_bytes()`

- [ ] **Step 1: Write failing tests for storage proportions and segmented bar creation**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement proportion calculations and CSS-styled `Gtk.Box` in `docker_janitor.py`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit `feat(hud): add segmented storage bar calculation and styling`**

---

### Task 2: `JanitorHudWindow` Component

**Files:**
- Modify: `docker_janitor.py`
- Modify: `tests/test_hud.py`

**Interfaces:**
- Produces: `class JanitorHudWindow(Gtk.Window)` with `position_near_tray()`, `on_key_press()`, `on_focus_out()`, and signal callbacks for clean and exit actions.
- Consumes: `Preview`, `build_segmented_bar()`

- [ ] **Step 1: Write failing tests for window initialization, Escape key, and focus-out**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `JanitorHudWindow` in `docker_janitor.py`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit `feat(hud): implement JanitorHudWindow with panel positioning and dismissal`**

---

### Task 3: Interactive Prune Workflow in HUD & App Integration

**Files:**
- Modify: `docker_janitor.py`
- Modify: `tests/test_hud.py`
- Modify: `tests/test_wire.py`

**Interfaces:**
- Produces: `JanitorApp.show_hud()`, updated `JanitorApp.on_run()` activating the HUD directly instead of Zenity.
- Consumes: `JanitorHudWindow`, `run_prune()`, `log_report()`, `notify_report()`

- [ ] **Step 1: Write failing tests asserting HUD opens on run and clean button triggers prune**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Wire HUD into `JanitorApp` and connect the clean button to the worker thread**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit `feat(hud): connect tray action directly to HUD with live cleanup feedback`**

---

### Task 4: Documentation, Service Restart & Final Verification

**Files:**
- Modify: `README.md`
- Modify: `PLAN.md`

- [ ] **Step 1: Update documentation and plan to reflect the native HUD**
- [ ] **Step 2: Run full test suite with broadway across all test files**
- [ ] **Step 3: Restart user desktop service `systemctl --user restart docker-janitor.service`**
- [ ] **Step 4: Verify live service status**
- [ ] **Step 5: Commit `docs: update documentation for native Popover HUD`**
