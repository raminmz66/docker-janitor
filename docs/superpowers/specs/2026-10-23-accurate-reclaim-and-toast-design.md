# Design Spec: Accurate Cleanup Estimation & Reclaim Feedback

## Context & Problem
In the user's desktop environment, running Docker Janitor opened the HUD indicating reclaimable space (~50 GB). When the cleanup action was triggered, `docker-janitor` executed:
1. `docker builder prune -af --filter until=168h`
2. `docker image prune -f`
3. `docker image prune -af --filter until=720h`

All commands returned `Total: 0B` reclaimed. The app then displayed a button label `"Cleaned 0 B!"` and fired a GNOME Shell notification:
> **Docker Janitor**
> Docker Janitor reclaimed 0 B.

This happened due to three distinct gaps between the preview estimation and Docker's actual prune engine:
1. **BuildKit Cache Dependency Hierarchy**: BuildKit evaluates cache records hierarchically. A parent cache layer cannot be pruned if any child/descendant layer was accessed within the `until` window (`< 168h`). `docker_janitor` previously evaluated records in isolation by creation date, ignoring that all 87 leaf records were accessed recently, protecting all 494 ancestor layers.
2. **Container Image Associations**: `docker image prune -a` preserves images associated with containers by image ID *or* configured repository name (`.Config.Image`). `docker_janitor` only checked exact image sha256 IDs, misclassifying images like `docker-dev-environment_apache2` as unused when a container was using that image tag.
3. **Misleading 0 B Notification & Button Feedback**: When `reclaimed_bytes == 0`, formatting the message as `"Docker Janitor reclaimed 0 B."` and `"Cleaned 0 B!"` implies a failed or buggy operation rather than stating clearly that the storage is already clean.

---

## Technical Solution

### 1. Accurate Container Image Association
- When querying container images, inspect both `{{.Image}}` and `{{.Config.Image}}`:
  ```bash
  docker container inspect --format "{{.Image}}|||{{.Config.Image}}" <ids...>
  ```
- Collect both resolved Image IDs and repository names / image tags (`used_names`).
- Mark an image as used if `image.id in used_ids`, `image.repository in used_names`, or `f"{image.repository}:{image.tag}" in used_names`.

### 2. Dependency-Aware Build Cache Estimation
- Parse `Parents:` in addition to `ID:`, `Created at:`, `Last used:`, `Size:`, `Reclaimable:`, and `Shared:` from `docker buildx du --verbose`.
- Determine local eligibility: `reclaimable and not shared and not is_recent(last_used, created, cutoff)`.
- Propagate protection: Any record that is not eligible (or is recent) is **protected**. Traverse up parent pointers to mark all ancestors of protected records as protected.
- Only records that are locally eligible AND not ancestors of any protected record are counted as prunable.

### 3. Clear 0 B Cleanup Feedback
- **Desktop Toast** (`notify_report`):
  - If `reclaimed_bytes == 0`: `"Docker storage is already clean (0 B reclaimed)."`
  - If `reclaimed_bytes > 0`: `"Docker Janitor reclaimed %s." % human_bytes(reclaimed_bytes)`
- **HUD Clean Button** (`_on_prune_complete`):
  - If `reclaimed_bytes == 0`: `"Already clean!"`
  - If `reclaimed_bytes > 0`: `"Cleaned %s!" % human_bytes(reclaimed_bytes)`

---

## Verification Plan
1. Unit tests for `parse_used_ids` / `parse_used_image_refs` with `{{.Image}}|||{{.Config.Image}}`.
2. Unit tests for dependency-tree cache prunability with protected children blocking ancestor pruning.
3. Unit tests for `notify_report` and HUD button label with `reclaimed_bytes == 0`.
4. Run full test suite with BroadWay/X11 display.
5. Live verification against user's Docker daemon: confirm `Preview.total_bytes == 0` and HUD displays "No Cleanup Needed".
