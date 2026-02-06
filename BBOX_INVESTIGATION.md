# Bounding Box Positioning Investigation

**Date:** February 5, 2026  
**Status:** Unresolved — pickup in future session

---

## Problem

Green bounding boxes overlaid on deer detection snapshots are consistently mispositioned on both dashboard thumbnail cards and modal views. The boxes do not land on the deer in the images. Accurate bbox overlay is critical for:
- Visual verification of detection quality
- Building reliable training/retraining datasets from snapshots, uploaded images, and extracted video frames

## What's Confirmed Working

### Stored bbox coordinates are correct
All pixel coords `{x1, y1, x2, y2}` in the `ring_events.detection_bboxes` column (SQLite, JSON text) are in the image's **native coordinate space**:
- Ring camera snapshots: 640x360
- Manual uploads: variable (e.g., 2796x1290 for #5766)
- Extracted video frames: variable

Server-side PIL verification (drawing bboxes directly on the actual image files) confirmed boxes land correctly on the deer. The problem is purely in frontend rendering.

### Data pipeline is intact
```
ML Detector (YOLO box.xyxy → {x1,y1,x2,y2}) 
  → Coordinator (passes through unchanged)
    → Backend (stores as JSON text in ring_events.detection_bboxes)
      → API (deserializes JSON, returns in response)
        → Frontend (BoundingBoxImage.jsx renders on canvas)
```

Format at every stage: `[{"confidence": float, "bbox": {"x1": float, "y1": float, "x2": float, "y2": float, "center_x": float, "center_y": float}}]`

### Coordinator now sends detection_bboxes
Fixed Feb 5, 2026 — the coordinator's PATCH to `/api/ring-events/{id}` previously only sent `processed`, `deer_detected`, `confidence`. Now includes `detection_bboxes` in the payload so new periodic snapshot detections get their bboxes stored.

## Sample Data Points

| ID | Image Size | Bbox (x1,y1)-(x2,y2) | Confidence | Source |
|----|-----------|----------------------|------------|--------|
| #19699 | 640x360 | (322.3, 144.9)-(393.0, 193.7) | 52% | Ring event snapshot |
| #17365 | 640x360 | (400.1, 111.9)-(452.7, 146.9) | 47% | Periodic snapshot |
| #17363 | 640x360 | (375.9, 113.5)-(457.3, 146.8) | 6% | Periodic snapshot |
| #17359 | 640x360 | (291.0, 123.5)-(372.5, 173.8) | 31% | Ring event snapshot |
| #5766 | 2796x1290 | (1703.8, 364.0)-(1932.1, 552.0) | 56% | Manual upload |

## Attempted Fixes (None Resolved the Issue)

### 1. Letterbox offset calculation (commit bf99230)
Added proper offset math for `object-fit: contain` to account for letterbox padding when image aspect ratio differs from container aspect ratio. Correct logic, but no visible change because 640x360 images in 16:9 containers have zero letterbox offset.

### 2. Container rect, block display, inline object-fit (commit 49b444c)
- Changed `.bounding-box-container` from `display: inline-block` to `display: block`
- Used container `getBoundingClientRect()` instead of image `getBoundingClientRect()` for canvas sizing
- Canvas pixel buffer dimensions explicitly matched to CSS dimensions (`canvas.style.width/height`)
- Forced `object-fit: contain` via inline style to eliminate CSS specificity conflicts with Dashboard.css (which sets `object-fit: cover` on `.snapshot-thumbnail img`)
- No visible change in bbox positioning

### 3. Confidence labels (commit 49b444c, reverted in 4194aea)
Added confidence percentage labels on bboxes. User didn't want them — removed.

## Re-Detection Issues (Observed Feb 5)

When clicking "yes-deer" to re-run detection on existing snapshots:

1. **#17363 and #17361 (640x360 Ring snapshots):** Re-detection produced **no visible bbox** and confidence dropped to 0%. The deer are clearly visible in these images. Possible causes:
   - Re-detection threshold may be too high
   - The re-detection endpoint may not be storing bboxes correctly
   - The `DeerDetector` class in `src/inference/detector.py` (used by backend's rerun-detection) vs the ML detector container's `/detect` endpoint may behave differently

2. **#5766 (2796x1290 manual upload):** Re-detection produced a bbox that was the **wrong shape and location** with 21% confidence (originally 56%). This suggests:
   - The re-detection may be using a different model or threshold
   - YOLO's internal letterbox resizing to 640x640 may produce different coordinates when re-running vs original detection
   - The backend's `DeerDetector` may handle large images differently than the ML detector container

## Current State of BoundingBoxImage.jsx

The component:
- Uses a `<canvas>` overlay absolutely positioned over an `<img>` element inside a container div
- Calculates scale as `containerWidth / image.naturalWidth` (for matching aspect ratios)
- Applies `object-fit: contain` via inline style
- Handles both YOLO normalized `[cx, cy, w, h]` and pixel `{x1, y1, x2, y2}` formats
- Redraws on resize via `requestAnimationFrame`

## CSS Context

```
.snapshot-thumbnail {         → position: relative; aspect-ratio: 16/9; background: #000
.snapshot-thumbnail img {     → width: 100%; height: 100%; object-fit: cover (OVERRIDDEN by inline style)
.bounding-box-container {     → position: relative; display: block; width: 100%; height: 100%; overflow: hidden
.bounding-box-container img { → display: block; width: 100%; height: 100%
.bounding-box-canvas {        → position: absolute; top: 0; left: 0; pointer-events: none
```

## Next Steps for Future Session

### High Priority
1. **Add debug logging to the browser.** Temporarily log `containerRect`, `naturalWidth/Height`, `scale`, `offsetX/Y`, and computed bbox `x, y, w, h` to the console. Compare against expected values to identify the math discrepancy.

2. **Inspect with browser DevTools.** Check the actual rendered layout of the container, image, and canvas elements. Verify canvas (0,0) aligns with the image content (0,0). Look for any unexpected margins, padding, or transforms.

3. **Test with a known reference.** Create a test image with a marker at known pixel coords, set a bbox at those coords, and see where it renders. Eliminates the variable of "is the deer actually where we think it is."

### Medium Priority
4. **Check `devicePixelRatio`.** On high-DPI displays, `getBoundingClientRect()` returns CSS pixels but the canvas buffer may need `window.devicePixelRatio` scaling for correct coordinate mapping.

5. **Investigate re-detection path.** The backend's `rerun-detection` endpoint uses `src/inference/detector.py` (`DeerDetector` class) while original detection goes through the ML detector container (`Dockerfile.ml-detector`). Verify they produce consistent results, especially for large images.

6. **Verify YOLO coordinate mapping.** YOLO internally resizes images to 640x640 with letterbox padding, but `box.xyxy` should be remapped to original image coordinates. Worth verifying with a direct test, especially for non-standard image sizes.

### Low Priority
7. **Consider alternative rendering approach.** Instead of canvas overlay, could draw bboxes as absolutely-positioned `<div>` elements with CSS borders. This would use the same coordinate system as the image layout and might be more robust.

## Files Involved

- `frontend/src/components/BoundingBoxImage.jsx` — Canvas overlay rendering
- `frontend/src/components/BoundingBoxImage.css` — Container and canvas styles
- `frontend/src/components/Dashboard.jsx` — Uses BoundingBoxImage at lines ~291 (thumbnails) and ~402 (modal)
- `frontend/src/components/Dashboard.css` — `.snapshot-thumbnail` styles (line 137)
- `Dockerfile.ml-detector` — ML detector container, YOLO inference (line ~236)
- `src/inference/detector.py` — Backend's DeerDetector class used by rerun-detection
- `backend/main.py` — Active backend (Docker uses `main.py`, not `main_server.py`)
- `backend/database.py` — `detection_bboxes` storage/retrieval (line ~813, ~872)
- `Dockerfile.coordinator` — Coordinator, now sends bboxes in PATCH (line ~428)
