# Docker Janitor: Instant Scanning HUD Design

## 1. Intent & Problem Statement
When a user clicks **Run** in the tray menu, Docker Janitor sequentially executes 7 Docker CLI inspection subcommands (`info`, `system df`, `images`, `ps`, `inspect`, `df -v`, and `buildx du --verbose`) before displaying any UI. On systems with hundreds of build cache records, this causes a 1 to 3 second dead-time with zero visual feedback, making users wonder if the app failed to launch or crashed.

## 2. Goals & Constraints
- **0ms Perceived Latency**: The HUD window appears immediately upon clicking **Run**.
- **Active Scanning State**: The window presents an active `Gtk.Spinner`, placeholder storage bar, and clear status text (`Scanning Docker storage...`).
- **In-Place Data Population**: When inspection completes in the worker thread, `set_preview(preview)` seamlessly swaps the placeholders for live numbers, the segmented bar, and the active `Free Now` button without changing window dimensions.
- **Error Gracefulness**: If Docker is unreachable, the window displays an inline error message with a Close action, and routes to desktop notifications without crashing.
- **Safety Invariant**: Preserves strictly on-demand execution (no continuous polling daemons).

## 3. Selected Approach
**Approach 1: Immediate HUD Window with Live In-Place Updates**
- `JanitorHudWindow(preview=None, ...)` initializes in scanning mode if `preview` is omitted.
- Window size request is fixed (width: 340px) so layout does not jump when live data loads.
- `JanitorApp.on_run()` displays the HUD immediately, then dispatches the background worker.
- Inspection results dispatch back to the GTK thread via `GLib.idle_add(self._on_preview_ready, preview)`.

## 4. UI States
1. **Scanning State**:
   - Title: `Docker Janitor` with whale icon and close button.
   - Hero: `Gtk.Spinner` (spinning) with text `"Scanning Docker storage..."`.
   - Bar: Neutral gray animated or placeholder bar.
   - Badge: `"Checking container & volume safety..."`.
   - Button: Disabled (`"Calculating Space..."`).
2. **Ready State (Loaded)**:
   - Hero: Large bold `24.4 GB` with subtitle.
   - Bar: Segmented color bar (Cache in `#0db7ed`, Images in `#ff9f0a`, Kept in gray).
   - Badge: `"🛡️ Protected: 6 volumes & 12 containers safe"`.
   - Button: Enabled (`"Free 24.4 GB Now"`).
3. **Error State**:
   - Hero: `"Docker Unavailable"`.
   - Subtitle: `"Docker daemon is not running or not responding."`.
   - Button: `"Close"`.

## 5. Verification Plan
- Unit tests in `tests/test_hud.py` verify initializing `JanitorHudWindow` without preview (scanning state) and calling `set_preview()`.
- Threading tests in `tests/test_wire.py` verify immediate window creation and in-place updates.
- Headless test discovery passes 100%.
