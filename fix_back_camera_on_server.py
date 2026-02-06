#!/usr/bin/env python3
import sqlite3
from pathlib import Path

DB_PATH = Path("/home/rndpig/deer-deterrent/backend/data/training.db")
BACK_CAMERA_ID = "f045dae9383a"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Get count
cursor.execute(
    "SELECT COUNT(*) FROM ring_events WHERE camera_id = ? AND deer_detected = 1",
    (BACK_CAMERA_ID,)
)
count = cursor.fetchone()[0]

print(f"Found {count} Back camera snapshots with deer_detected=1")

if count > 0:
    # Update to deer_detected=0
    cursor.execute(
        "UPDATE ring_events SET deer_detected = 0, detection_confidence = 0.0 WHERE camera_id = ? AND deer_detected = 1",
        (BACK_CAMERA_ID,)
    )
    conn.commit()
    print(f"✅ Updated {count} snapshots to deer_detected=0")
else:
    print("No snapshots to update")

conn.close()
