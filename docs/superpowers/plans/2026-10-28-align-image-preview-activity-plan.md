# Implementation Plan: Align Image Preview with Docker Activity & Prune Filter

## Overview
Prevent preview/cleanup inconsistency by ensuring Docker Janitor queries Docker's `until` filter criteria when selecting unused images for preview.

---

## Tasks

### Task 1: Add Unit Tests for `parse_image_ids` and `_matches_eligible_ids`
- File: `tests/test_inspect.py`
- Test cases:
  - Exact match of short image IDs.
  - Prefix matching between short IDs (12 chars) and long sha256 IDs.
  - Empty set of eligible IDs returns False.
  - `eligible_ids=None` returns True (fallback mode).

### Task 2: Update `unused_images` to Support `eligible_ids` Filter
- File: `docker_janitor.py`
- Add `parse_image_ids(text)` and `_matches_eligible_ids(image_id, eligible_ids)`.
- Update `unused_images(images, used_ids, now, min_age_days, eligible_ids=None)`:
  - If `eligible_ids is not None`, filter images using `_matches_eligible_ids(image.id, eligible_ids)`.
  - If `eligible_ids is None`, fall back to `image.created < cutoff`.
- Add unit tests in `tests/test_inspect.py` verifying that recently tagged images with older creation dates are excluded when `eligible_ids` does not include them.

### Task 3: Update `collect_preview` and `FakeDocker` in Preview Tests
- Files: `docker_janitor.py`, `tests/test_preview.py`
- In `collect_preview`:
  - Run `runner("images", "-a", "--filter", "until=%dh" % (config.image_min_age_days * 24), "-q")` inside a `try...except DockerError` block.
  - Pass `eligible_ids` to `unused_images`.
- In `tests/test_preview.py`:
  - Update `FakeDocker` to respond to `images -a --filter until=... -q`.
  - Verify `CollectPreviewTests` continues to pass with fixture data.
  - Add test verifying fallback behavior when `images -a --filter until=... -q` raises `DockerError`.

### Task 4: Live Verification & Local Installation Update
- Run full unit test suite: `python3 -m unittest discover -s tests`.
- Run live preview check on user's system to ensure `Preview.image_bytes == 0` and consistent status.
- Run `./install.sh` to update the installed app in `~/.local/bin/docker-janitor`.
- Merge feature branch with squash, push to `origin/main`, and clean up branch.
