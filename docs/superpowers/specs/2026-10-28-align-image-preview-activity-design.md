# Design Spec: Align Image Preview with Docker Activity & Prune Filter

## 1. Context & Problem Statement
In Docker Janitor, the preview calculation and the actual cleanup execution differed in how they determined an image's age:
- **Preview Query (`collect_preview` / `unused_images`)**: Examined the `CreatedAt` field from `docker images --format '{{json .}}'`, which reflects the upstream build creation date of the image.
- **Cleanup Prune Command (`prune_commands`)**: Ran `docker image prune -af --filter until=<X>h`. Docker Engine's `until` filter evaluates images based on the local tag, pull, or snapshot activity timestamp (`Metadata.LastTagTime` or daemon activity timestamp).

### Observed Failure Mode
When an image (e.g. `dunglas/mercure:latest`) was built upstream 33 days ago (September 25) but pulled/tagged locally 28.9 days ago (September 29):
1. `collect_preview` evaluated `image.created < cutoff` (33 days > 30-day threshold) and flagged the image as reclaimable (202.0 MB).
2. The HUD displayed: "Free 202.0 MB Now".
3. When the user clicked "Free 202.0 MB Now", `docker image prune -af --filter until=720h` ran. Docker Engine checked the image's local activity (< 720h), and refused to delete it.
4. Total reclaimed space was 0 B. Docker Janitor posted a notification: "Docker storage is already clean (0 B reclaimed)."
5. Re-running immediately detected the exact same 202.0 MB, creating an infinite inconsistency loop.

---

## 2. Decision: Approach 1 (Strict Activity-Based Consistency)
Align preview evaluation with Docker Engine's `until` filter:
- When checking images eligible for pruning under `IMAGE_MIN_AGE_DAYS`, query Docker Engine directly for images that satisfy the `--filter until=<hours>` condition via `docker images -a --filter until=<hours> -q`.
- Only images reported by Docker Engine as satisfying the `until` criteria (and not referenced by any running/stopped container or tag) are counted as reclaimable.
- Graceful Fallback: If `docker images -a --filter until=... -q` fails or is run in a mocked/legacy environment without filter support, fall back safely to `image.created < cutoff`.

### Security & Safety Properties
- **Zero Accidental Deletions**: Images downloaded or tagged recently by the developer are protected from premature cleanup, honoring the user's active retention window.
- **100% Preview-Prune Consistency**: If an image is not eligible to be deleted by `docker image prune -af --filter until=<X>h`, it will never be reported as reclaimable in the HUD.
- **Self-Healing**: Once the local pull/tag time reaches 30 days, both the preview and Docker Engine's prune command will simultaneously recognize it as eligible, freeing the space without contradiction.

---

## 3. Detailed Technical Design

### 3.1 Docker Inspection
In `collect_preview(config, runner, now)`:
```python
eligible_ids = None
try:
    until_hours = config.image_min_age_days * 24
    raw_ids = runner("images", "-a", "--filter", "until=%dh" % until_hours, "-q")
    eligible_ids = parse_image_ids(raw_ids)
except DockerError:
    eligible_ids = None
```

### 3.2 ID Matching Helper
```python
def parse_image_ids(text):
    return {line.strip() for line in (text or "").splitlines() if line.strip()}

def _matches_eligible_ids(image_id, eligible_ids):
    if eligible_ids is None:
        return True
    if not eligible_ids:
        return False
    clean_id = image_id.removeprefix("sha256:")
    for eid in eligible_ids:
        clean_eid = eid.removeprefix("sha256:")
        if clean_id.startswith(clean_eid) or clean_eid.startswith(clean_id):
            return True
    return False
```

### 3.3 Selection Logic
In `unused_images(images, used_ids, now, min_age_days, eligible_ids=None)`:
```python
cutoff = now - timedelta(days=min_age_days)
return [
    image
    for image in images
    if image.id not in used_ids
    and image.repository not in used_ids
    and ("%s:%s" % (image.repository, image.tag)) not in used_ids
    and not (image.repository == "<none>" and image.tag == "<none>")
    and (
        _matches_eligible_ids(image.id, eligible_ids)
        if eligible_ids is not None
        else image.created < cutoff
    )
]
```

---

## 4. Edge Cases Considered
1. **Dangling Images**: Handled separately via `dangling_images(images)` and pruned via `docker image prune -f` without age restriction.
2. **Short vs Full Sha256 IDs**: IDs from `docker images -q` can be 12-character prefixes while `image.id` or inspect might have prefixes or full 64-character hashes. `_matches_eligible_ids` normalizes both by stripping `sha256:` and testing bidirectional prefix matching (`clean_id.startswith(clean_eid) or clean_eid.startswith(clean_id)`).
3. **Empty Eligible List**: If Docker returns an empty set of IDs for `until`, `eligible_ids = set()`, and `_matches_eligible_ids` returns `False`, correctly resulting in 0 images selected.
4. **Mocked / Offline Testing**: If `eligible_ids is None`, behavior gracefully falls back to `image.created < cutoff`, maintaining compatibility with test fixtures.

---

## 5. Verification Plan
1. **Unit Tests**:
   - Test `_matches_eligible_ids` with short IDs, full sha256 IDs, empty set, and `None`.
   - Test `unused_images` with `eligible_ids` restricting old build dates that were recently pulled/tagged.
   - Update `CollectPreviewTests` in `tests/test_preview.py` to support `images -a --filter until=... -q`.
2. **Live Verification**:
   - Run `collect_preview` on live Docker daemon: verify `Preview.image_bytes == 0` and HUD displays "No Cleanup Needed".
   - Test with artificial threshold (`IMAGE_MIN_AGE_DAYS=20`): verify older images are detected properly.
3. **Packaging / Installation Update**:
   - Run `./install.sh` to update the local installation in `~/.local/bin/docker-janitor`.
