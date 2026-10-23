# Implementation Plan: Accurate Cleanup Estimation & Reclaim Feedback

**Goal:** Ensure Docker Janitor preview calculations perfectly mirror Docker prune semantics (dependency-tree cache reachability and container name associations), and present clear, user-friendly feedback when 0 B is reclaimed.

## User Review Focus
- When Docker storage has no prunable items, the HUD displays "0 B", subtitle "Docker storage is clean", and the button is disabled with "No Cleanup Needed".
- If prune ever runs and reclaims 0 B, the notification and button clearly state "Docker storage is already clean (0 B reclaimed)" and "Already clean!".

---

### Task 1: 0 B Notification and Button Feedback

**Files:**
- Modify: `docker_janitor.py`
- Modify: `tests/test_prune.py`
- Modify: `tests/test_wire.py`

**Steps:**
- [x] Write tests in `test_prune.py` asserting `notify_report` formats 0 B as "Docker storage is already clean (0 B reclaimed)."
- [x] Implement conditional notification message in `notify_report`.
- [x] Update `_on_prune_complete` in `docker_janitor.py` to label the button "Already clean!" when 0 B reclaimed.
- [x] Run tests to verify pass.
- [x] Commit `fix(notify): format 0 B cleanup notification and button label as already clean`.

---

### Task 2: Container Image Association with Config.Image

**Files:**
- Modify: `docker_janitor.py`
- Modify: `tests/test_inspect.py`
- Modify: `tests/test_preview.py`

**Steps:**
- [x] Write unit test in `test_inspect.py` verifying images referenced by container repository names (`.Config.Image`) are treated as used.
- [x] Update `collect_preview()` and `unused_images()` to inspect `{{.Image}}|||{{.Config.Image}}` and check repository/tag matching.
- [x] Run tests to verify pass.
- [x] Commit `fix(inspect): consider container Config.Image references when detecting unused images`.

---

### Task 3: Dependency-Aware Build Cache Estimation

**Files:**
- Modify: `docker_janitor.py`
- Modify: `tests/test_inspect.py`

**Steps:**
- [x] Write unit test in `test_inspect.py` with parent-child cache records verifying that a recently-used child prevents its parent records from being counted as prunable.
- [x] Update `parse_cache_records` to parse `Parents:` and `Last used:`.
- [x] Update `prunable_cache` to build the DAG and propagate protection up parent chains.
- [x] Run tests to verify pass.
- [x] Commit `fix(inspect): implement dependency-aware build cache pruning estimation`.

---

### Task 4: Full Suite Verification & Live Validation

**Files:**
- Modify: `docs/superpowers/plans/2026-10-23-accurate-reclaim-and-toast.md`

**Steps:**
- [x] Run full test suite across all test files.
- [x] Restart user desktop service `systemctl --user restart docker-janitor.service`.
- [x] Verify live preview on user machine reports 0 B reclaimable with disabled clean button.
- [x] Commit `docs: record accurate reclaim and toast verification`.
