#!/usr/bin/env python3
"""
Benchmark v4.0 model against snapshots with human-verified deer presence.

Runs each snapshot through the live ml-detector API and compares results
against existing human annotations. Does NOT modify any original data.

Two groups reported separately:
  Group 1: Snapshots with manual bounding boxes (confidence: null in bbox JSON)
  Group 2: User-confirmed snapshots (user_confirmed=1) without manual bboxes

Output: Console summary + CSV file with per-snapshot results.

Usage (run on Dell server):
    python3 scripts/benchmark_v4_vs_manual.py
    python3 scripts/benchmark_v4_vs_manual.py --output /tmp/benchmark_results.csv
    python3 scripts/benchmark_v4_vs_manual.py --threshold 0.55
"""

import argparse
import csv
import json
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

# Paths
DB_PATH = Path("/home/rndpig/deer-deterrent/backend/data/training.db")
SNAPSHOT_DIRS = [
    Path("/home/rndpig/deer-deterrent/dell-deployment/data/snapshots"),
    Path("/home/rndpig/deer-deterrent/backend/data/snapshots"),
]
ML_DETECTOR_URL = "http://localhost:8001"

DEFAULT_OUTPUT = f"/home/rndpig/deer-deterrent/logs/benchmark_v4_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"


def find_snapshot(snapshot_path: str) -> Path | None:
    """Resolve a DB snapshot_path to an actual file on disk."""
    # DB stores paths like "snapshots/periodic_20260322_022619_c4dbad08f862.jpg"
    filename = Path(snapshot_path).name
    for d in SNAPSHOT_DIRS:
        candidate = d / filename
        if candidate.exists():
            return candidate
    return None


def has_manual_bbox(bboxes_json: str) -> bool:
    """Check if bbox JSON contains any manual (confidence: null) entries."""
    if not bboxes_json:
        return False
    try:
        bboxes = json.loads(bboxes_json)
        return any(b.get("confidence") is None for b in bboxes)
    except (json.JSONDecodeError, TypeError):
        return False


def detect_image(image_path: Path) -> dict:
    """Send image to ml-detector /detect endpoint and return results."""
    with open(image_path, "rb") as f:
        resp = requests.post(
            f"{ML_DETECTOR_URL}/detect",
            files={"file": (image_path.name, f, "image/jpeg")},
            timeout=30,
        )
    resp.raise_for_status()
    return resp.json()


def compute_iou(box_a: dict, box_b: dict) -> float:
    """Compute IoU between two bboxes in {x1,y1,x2,y2} format."""
    x1 = max(box_a["x1"], box_b["x1"])
    y1 = max(box_a["y1"], box_b["y1"])
    x2 = min(box_a["x2"], box_b["x2"])
    y2 = min(box_a["y2"], box_b["y2"])

    inter = max(0, x2 - x1) * max(0, y2 - y1)
    if inter == 0:
        return 0.0

    area_a = (box_a["x2"] - box_a["x1"]) * (box_a["y2"] - box_a["y1"])
    area_b = (box_b["x2"] - box_b["x1"]) * (box_b["y2"] - box_b["y1"])
    return inter / (area_a + area_b - inter)


def best_iou_for_manual(manual_bboxes: list, detected_bboxes: list) -> float:
    """For each manual bbox, find best IoU with any detected bbox. Return average."""
    if not manual_bboxes or not detected_bboxes:
        return 0.0
    ious = []
    for mb in manual_bboxes:
        best = max(compute_iou(mb, db) for db in detected_bboxes)
        ious.append(best)
    return sum(ious) / len(ious)


def main():
    parser = argparse.ArgumentParser(description="Benchmark v4.0 model against manual annotations")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output CSV path")
    parser.add_argument("--threshold", type=float, default=None,
                        help="Override confidence threshold (default: use ml-detector's current setting)")
    args = parser.parse_args()

    # Check ml-detector health
    try:
        health = requests.get(f"{ML_DETECTOR_URL}/health", timeout=5).json()
        model_version = health.get("model_version", "unknown")
        current_threshold = health.get("confidence_threshold", "unknown")
        print(f"  ml-detector: {model_version}, threshold={current_threshold}")
    except Exception as e:
        print(f"ERROR: Cannot reach ml-detector at {ML_DETECTOR_URL}: {e}")
        sys.exit(1)

    # Query snapshots
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, snapshot_path, detection_bboxes, detection_confidence,
               user_confirmed, camera_id, timestamp, model_version
        FROM ring_events
        WHERE deer_detected = 1
          AND (detection_bboxes LIKE '%null%' OR user_confirmed = 1)
        ORDER BY timestamp
    """)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("  No matching snapshots found.")
        return

    # Classify into groups
    group1 = []  # manual bboxes
    group2 = []  # user_confirmed without manual bboxes
    skipped_no_file = 0

    for row in rows:
        image_path = find_snapshot(row["snapshot_path"]) if row["snapshot_path"] else None
        if not image_path:
            skipped_no_file += 1
            continue

        entry = dict(row)
        entry["image_path"] = str(image_path)

        if has_manual_bbox(row["detection_bboxes"]):
            group1.append(entry)
        elif row["user_confirmed"] == 1:
            group2.append(entry)

    print(f"\n  Found {len(group1)} snapshots with manual bboxes")
    print(f"  Found {len(group2)} user-confirmed snapshots (no manual bboxes)")
    if skipped_no_file > 0:
        print(f"  Skipped {skipped_no_file} (snapshot file not found on disk)")

    # Run detections
    results = []
    total = len(group1) + len(group2)

    for idx, entry in enumerate(group1 + group2, 1):
        group_label = "manual_bbox" if entry in group1 else "user_confirmed"
        event_id = entry["id"]
        image_path = Path(entry["image_path"])

        print(f"  [{idx}/{total}] Event {event_id} ({group_label})...", end=" ", flush=True)

        try:
            result = detect_image(image_path)
            deer_detected = result.get("deer_detected", False)
            new_detections = result.get("detections", [])
            new_confidence = max((d["confidence"] for d in new_detections), default=0)

            # Extract bboxes from detections
            new_bboxes = [d["bbox"] for d in new_detections if "bbox" in d]

            # Parse original manual bboxes
            orig_bboxes = []
            manual_bboxes = []
            if entry["detection_bboxes"]:
                try:
                    orig_bboxes = json.loads(entry["detection_bboxes"])
                    manual_bboxes = [b["bbox"] for b in orig_bboxes if b.get("confidence") is None]
                except (json.JSONDecodeError, TypeError):
                    pass

            # Compute IoU if we have manual bboxes and new detections
            avg_iou = best_iou_for_manual(manual_bboxes, new_bboxes) if manual_bboxes and new_bboxes else None

            status = "HIT" if deer_detected else "MISS"
            print(f"{status} conf={new_confidence:.3f}" + (f" IoU={avg_iou:.3f}" if avg_iou is not None else ""))

            results.append({
                "event_id": event_id,
                "group": group_label,
                "camera_id": entry["camera_id"],
                "timestamp": entry["timestamp"],
                "snapshot": Path(entry["snapshot_path"]).name if entry["snapshot_path"] else "",
                "original_confidence": entry["detection_confidence"],
                "original_model": entry["model_version"] or "",
                "original_bbox_count": len(orig_bboxes),
                "manual_bbox_count": len(manual_bboxes),
                "v4_detected": deer_detected,
                "v4_confidence": round(new_confidence, 4) if new_confidence else 0,
                "v4_bbox_count": len(new_bboxes),
                "v4_bboxes_json": json.dumps(new_detections),
                "avg_iou": round(avg_iou, 4) if avg_iou is not None else "",
            })

        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "event_id": event_id,
                "group": group_label,
                "camera_id": entry["camera_id"],
                "timestamp": entry["timestamp"],
                "snapshot": Path(entry["snapshot_path"]).name if entry["snapshot_path"] else "",
                "original_confidence": entry["detection_confidence"],
                "original_model": entry["model_version"] or "",
                "original_bbox_count": 0,
                "manual_bbox_count": 0,
                "v4_detected": False,
                "v4_confidence": 0,
                "v4_bbox_count": 0,
                "v4_bboxes_json": "",
                "avg_iou": "",
                "error": str(e),
            })

    # Write CSV
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "event_id", "group", "camera_id", "timestamp", "snapshot",
        "original_confidence", "original_model", "original_bbox_count",
        "manual_bbox_count", "v4_detected", "v4_confidence", "v4_bbox_count",
        "v4_bboxes_json", "avg_iou",
    ]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    print(f"\n  Results written to: {output_path}")

    # Print summaries
    for group_name, label in [("manual_bbox", "Group 1: Manual Bboxes"), ("user_confirmed", "Group 2: User-Confirmed Only")]:
        group_results = [r for r in results if r["group"] == group_name]
        if not group_results:
            continue

        detected = sum(1 for r in group_results if r["v4_detected"])
        missed = len(group_results) - detected
        confs = [r["v4_confidence"] for r in group_results if r["v4_detected"]]
        avg_conf = sum(confs) / len(confs) if confs else 0
        ious = [r["avg_iou"] for r in group_results if r["avg_iou"] != "" and r["avg_iou"] is not None]
        avg_iou = sum(ious) / len(ious) if ious else 0

        print(f"\n  {'='*60}")
        print(f"  {label}")
        print(f"  {'='*60}")
        print(f"    Total snapshots:   {len(group_results)}")
        print(f"    v4.0 detected:     {detected} ({100*detected/len(group_results):.1f}%)")
        print(f"    v4.0 missed:       {missed} ({100*missed/len(group_results):.1f}%)")
        if confs:
            print(f"    Avg confidence:    {avg_conf:.4f}")
            print(f"    Min confidence:    {min(confs):.4f}")
            print(f"    Max confidence:    {max(confs):.4f}")
        if ious:
            print(f"    Avg IoU (manual):  {avg_iou:.4f}")

        # Show misses
        if missed > 0:
            print(f"\n    Missed snapshots:")
            for r in group_results:
                if not r["v4_detected"]:
                    print(f"      Event {r['event_id']}: {r['snapshot']} (orig conf={r['original_confidence']})")

    print(f"\n  {'='*60}")
    print(f"  Benchmark complete. Model: {model_version}")
    print(f"  {'='*60}")


if __name__ == "__main__":
    main()
