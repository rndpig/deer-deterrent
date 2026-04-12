#!/usr/bin/env python3
"""
Re-detect historical snapshots through the fixed ml-detector API.

After the RGB→BGR color space fix (2026-04-11), this script re-runs all
deer_detected=0 snapshots from enabled cameras through the ml-detector API
and updates events where deer are now detected.

Reports:
  - How many previously-missed events now show deer
  - Per-camera breakdown
  - Confidence distribution of new detections
  - CSV of all newly-detected events

Usage (run on Dell server):
    python3 scripts/redetect_historical.py
    python3 scripts/redetect_historical.py --dry-run          # don't update DB
    python3 scripts/redetect_historical.py --camera c4dbad08f862  # one camera only
    python3 scripts/redetect_historical.py --since 2026-04-01    # date filter
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests library required. pip install requests")
    sys.exit(1)

# Configuration
DB_PATH = Path("/home/rndpig/deer-deterrent/backend/data/training.db")
SNAPSHOT_DIR = Path("/home/rndpig/deer-deterrent/dell-deployment/data/snapshots")
ML_DETECTOR_URL = "http://localhost:8001"
BACKEND_URL = "http://localhost:8000"
LOG_DIR = Path("/home/rndpig/deer-deterrent/logs")

# Camera name mapping
CAMERA_NAMES = {
    "c4dbad08f862": "Side",
    "10cea9e4511f": "Woods",
    "587a624d3fae": "Driveway",
    "4439c4de7a79": "Front Door",
    "f045dae9383a": "Back",
}

# Enabled cameras for detection
ENABLED_CAMERAS = ["c4dbad08f862", "10cea9e4511f"]


def get_api_key():
    """Read INTERNAL_API_KEY from .env file."""
    env_path = Path("/home/rndpig/deer-deterrent/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("INTERNAL_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.getenv("INTERNAL_API_KEY", "")


def find_snapshot(snapshot_path: str) -> Path | None:
    """Resolve a DB snapshot_path to an actual file."""
    filename = Path(snapshot_path).name
    candidate = SNAPSHOT_DIR / filename
    if candidate.exists():
        return candidate
    return None


def detect_image(image_path: Path, api_key: str) -> dict:
    """Send image to ml-detector and return results."""
    headers = {}
    if api_key:
        headers["X-API-Key"] = api_key
    with open(image_path, "rb") as f:
        resp = requests.post(
            f"{ML_DETECTOR_URL}/detect",
            files={"file": (image_path.name, f, "image/jpeg")},
            headers=headers,
            timeout=30,
        )
    resp.raise_for_status()
    return resp.json()


def update_event(event_id: int, detections: list, confidence: float,
                 model_version: str, api_key: str) -> bool:
    """PATCH the backend to update a ring event with new detection results."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    payload = {
        "deer_detected": 1,
        "confidence": confidence,
        "detection_bboxes": detections,
        "model_version": f"{model_version} (redetect)",
    }
    resp = requests.patch(
        f"{BACKEND_URL}/api/ring-events/{event_id}",
        json=payload,
        headers=headers,
        timeout=10,
    )
    return resp.status_code == 200


def main():
    parser = argparse.ArgumentParser(description="Re-detect historical snapshots with fixed ml-detector")
    parser.add_argument("--dry-run", action="store_true", help="Don't update DB, just report")
    parser.add_argument("--camera", help="Limit to one camera ID")
    parser.add_argument("--since", help="Only events after this date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, default=0, help="Max events to process (0=all)")
    args = parser.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("WARNING: No API key found, requests may fail auth")

    # Check ml-detector health
    try:
        health = requests.get(f"{ML_DETECTOR_URL}/health", timeout=5).json()
        model_version = health.get("model_version", "unknown")
        threshold = health.get("confidence_threshold", "?")
        print(f"  ml-detector: {model_version}, threshold={threshold}")
    except Exception as e:
        print(f"ERROR: ml-detector not reachable: {e}")
        sys.exit(1)

    # Query non-deer events from enabled cameras
    cameras = [args.camera] if args.camera else ENABLED_CAMERAS
    placeholders = ",".join(["?"] * len(cameras))

    query = f"""
        SELECT id, timestamp, camera_id, snapshot_path, event_type,
               detection_confidence, model_version
        FROM ring_events
        WHERE deer_detected = 0
          AND snapshot_path IS NOT NULL AND snapshot_path != ''
          AND camera_id IN ({placeholders})
    """
    params = list(cameras)

    if args.since:
        query += " AND timestamp >= ?"
        params.append(args.since)

    query += " ORDER BY timestamp ASC"

    if args.limit:
        query += f" LIMIT {args.limit}"

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(query, params).fetchall()
    conn.close()

    total = len(rows)
    print(f"  Found {total} non-deer events to re-detect")
    if args.dry_run:
        print("  ** DRY RUN — no DB updates **")
    print()

    # Process
    new_detections = []
    missing_files = 0
    errors = 0
    start_time = time.time()

    for i, row in enumerate(rows, 1):
        event_id = row["id"]
        snapshot_path = row["snapshot_path"]
        camera_id = row["camera_id"]
        camera_name = CAMERA_NAMES.get(camera_id, camera_id)

        image_path = find_snapshot(snapshot_path)
        if not image_path:
            missing_files += 1
            continue

        try:
            result = detect_image(image_path, api_key)
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ERROR [{i}/{total}] Event {event_id}: {e}")
            if errors == 5:
                print("  (suppressing further error messages)")
            continue

        deer_detected = result.get("deer_detected", False)
        detections = result.get("detections", [])
        max_conf = max((d["confidence"] for d in detections), default=0)

        if deer_detected:
            # Format bboxes for DB storage
            bboxes = [{"confidence": d["confidence"], "bbox": d["bbox"]} for d in detections]

            if not args.dry_run:
                update_event(event_id, bboxes, max_conf, model_version, api_key)

            new_detections.append({
                "event_id": event_id,
                "timestamp": row["timestamp"],
                "camera_id": camera_id,
                "camera_name": camera_name,
                "event_type": row["event_type"],
                "confidence": max_conf,
                "num_boxes": len(detections),
                "snapshot": Path(snapshot_path).name,
                "old_confidence": row["detection_confidence"] or 0,
                "old_model": row["model_version"] or "",
            })
            print(f"  [{i}/{total}] Event {event_id} ({camera_name}): NEW DEER conf={max_conf:.3f} ({len(detections)} boxes)")

        # Progress every 200 events
        if i % 200 == 0:
            elapsed = time.time() - start_time
            rate = i / elapsed
            eta = (total - i) / rate if rate > 0 else 0
            found_so_far = len(new_detections)
            print(f"  --- Progress: {i}/{total} ({i/total*100:.0f}%), {found_so_far} new detections, ETA {eta/60:.1f}min ---")

    elapsed = time.time() - start_time

    # Write CSV
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = LOG_DIR / f"redetect_{timestamp_str}.csv"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if new_detections:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=new_detections[0].keys())
            writer.writeheader()
            writer.writerows(new_detections)

    # Summary
    print()
    print("=" * 60)
    print("  RE-DETECTION SUMMARY")
    print("=" * 60)
    print(f"  Total events scanned:    {total}")
    print(f"  Missing snapshot files:  {missing_files}")
    print(f"  API errors:              {errors}")
    print(f"  Previously no-deer:      {total - missing_files - errors}")
    print(f"  NEW deer detections:     {len(new_detections)}")
    if total > 0:
        print(f"  New detection rate:      {len(new_detections)/(total-missing_files-errors)*100:.1f}%")
    print(f"  Time elapsed:            {elapsed/60:.1f} min ({elapsed/total:.1f}s/image)" if total else "")
    print(f"  Mode:                    {'DRY RUN' if args.dry_run else 'LIVE (DB updated)'}")

    if new_detections:
        # Per-camera breakdown
        print()
        print("  Per-camera breakdown:")
        by_camera = {}
        for d in new_detections:
            cam = d["camera_name"]
            by_camera.setdefault(cam, []).append(d["confidence"])
        for cam, confs in sorted(by_camera.items()):
            avg = sum(confs) / len(confs)
            print(f"    {cam:15s}: {len(confs):4d} new detections, avg conf={avg:.3f}, min={min(confs):.3f}, max={max(confs):.3f}")

        # Confidence distribution
        all_confs = [d["confidence"] for d in new_detections]
        print()
        print("  Confidence distribution:")
        for lo, hi in [(0.55, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0)]:
            count = sum(1 for c in all_confs if lo <= c < hi)
            if count:
                print(f"    {lo:.2f}-{hi:.2f}: {count}")

        print(f"\n  CSV written to: {csv_path}")
    else:
        print("\n  No new deer detections found.")

    print("=" * 60)


if __name__ == "__main__":
    main()
