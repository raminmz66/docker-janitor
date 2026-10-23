# Docker Janitor: Native Popover HUD Design

## 1. Intent & Context
Docker Janitor currently uses a minimal `zenity` question dialog to display storage numbers. While functionally complete and safe, the user experience feels disjointed from the top panel tray icon.

This design introduces a **Native GTK3 Popover HUD** anchored directly beneath the top panel indicator, providing an immediate, modern, glanceable storage card with one-click cleanup.

---

## 2. Goals, Non-Goals, and Anti-Goals

### Goals
- **Direct Panel Access**: Clicking the panel whale opens the HUD card directly anchored near the top-right tray area.
- **Glanceable Storage Metrics**:
  - Prominent headline stat (e.g., `24.4 GB Reclaimable`).
  - Segmented multi-color bar: Build Cache (blue), Unused Images (orange), In-use & Protected (neutral gray).
  - Clear legend showing exact byte counts for each slice.
- **Safety Reassurance**: Visible badge confirming containers and volumes are strictly kept safe.
- **Single-Click Cleanup**: One prominent `Free <Size> Now` action button.
- **Clean Dismissal**: Closes automatically when clicking outside the window (`focus-out-event`) or pressing `Escape`.
- **Integrated Exit**: Subtle exit option (e.g. corner button) to quit the background tray app.

### Non-Goals
- Per-file or per-layer selective tree view (ruled out in brainstorming in favor of the streamlined HUD).
- Web-based frontend or external Electron/Qt runtimes (preserves zero-dependency GTK3/Python3 stack).

### Anti-Goals
- Modal dialogs that lock desktop focus.
- Freezing the GTK main loop during inspection or pruning (threading with `GLib.idle_add` is preserved).

---

## 3. Evaluated Approaches

1. **Approach 1: Frameless GTK Top-Level Window Anchored to Panel (Selected)**
   - *Architecture*: A custom `Gtk.Window` configured as a floating card (`decorated=False`, `type_hint=Gdk.WindowTypeHint.POPUP_MENU` or `UTILITY`), styled via GTK CSS. Position calculated from primary monitor workarea (top-right corner beneath standard panel height).
   - *Trade-offs*: Pixel-level visual control matching the mockup, smooth animations, and clean CSS styling. Handles click-away dismissal via `focus-out-event`.

2. **Approach 2: Centered Desktop Floating Dialog**
   - *Architecture*: Standard centered dialog with modern styling.
   - *Trade-offs*: Avoids geometry positioning, but fails the user's desire for a panel-attached popover experience.

3. **Approach 3: Custom Embedded Widgets inside DBusMenu**
   - *Architecture*: Embedding GTK boxes inside `Gtk.MenuItem`.
   - *Trade-offs*: Rejected. Modern GNOME Shell `appindicator` uses DBusMenu serialization, which strips custom GTK widgets and only passes plain text strings.

---

## 4. UI/UX Specification

### Layout Structure
```
+--------------------------------------------------+
|  [🐋 Docker Janitor]                  [Exit (✕)] |
|                                                  |
|                   24.4 GB                        |
|       Reclaimable without affecting projects     |
|                                                  |
|  [==== Cache: 20.8GB ===][= Images: 3.6GB =][===]|
|   ● Cache: 20.8 GB       ● Images: 3.6 GB        |
|                                                  |
|  [🛡️ Protected: 6 volumes & 12 containers safe]  |
|                                                  |
|            [   Free 24.4 GB Now   ]              |
+--------------------------------------------------+
```

### Visual Styling (GTK CSS)
- Dark and light theme responsive using system GTK theme palette.
- Background: `@theme_base_color` with subtle border and box-shadow.
- Segmented bar: CSS-styled joined boxes with rounded pill ends.
- Primary Action Button: Accent colored (`#0db7ed`) with hover states and active spinner during prune execution.

### Window Positioning & Lifecycle
1. User activates tray indicator.
2. `JanitorApp` queries Docker state asynchronously; if the popover is already open, it refreshes.
3. Window positions at `(monitor_x + monitor_width - window_width - 16, monitor_y + 36)` (aligned with panel height).
4. Window presents and grabs focus.
5. Clicking `Free Now` transitions the button to a spinner/busy state and launches `run_prune` on the worker thread.
6. Upon completion, displays a brief success toast and automatically dismisses the popover.

---

## 5. Verification & Testing
- Unit tests verify window instantiation, data binding with `Preview`, and close-on-escape / focus loss.
- Verification commands:
  - `python3 -m py_compile docker_janitor.py`
  - `python3 -m unittest discover -s tests -v`
  - Live inspection in GNOME session.
