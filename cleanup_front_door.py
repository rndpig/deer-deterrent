#!/usr/bin/env python3
"""Remove Front Door false positive detection."""
import sqlite3

DB_PATH = "/home/rndpig/deer-deterrent/backend/data/training.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Delete Front Door detections
cursor.execute("""
    DELETE FROM ring_events 
    WHERE deer_detected = 1 
    AND camera_id = '4439c4de7a79'
""")

deleted = cursor.rowcount
conn.commit()
conn.close()

print(f"✅ Deleted {deleted} Front Door detection(s)")
