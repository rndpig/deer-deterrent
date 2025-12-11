"""Diagnose database state for video 28."""
import sys
import sqlite3
from pathlib import Path

DB_PATH = Path("/home/rndpig/deer-deterrent/data/training.db")

if not DB_PATH.exists():
    print(f"❌ Database not found at {DB_PATH}")
    sys.exit(1)

print(f"✓ Database found at {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check video 28
cursor.execute("SELECT * FROM videos WHERE id = 28")
video = cursor.fetchone()

if not video:
    print("❌ Video 28 not found")
    sys.exit(1)

print(f"\n=== VIDEO 28 ===")
print(f"Filename: {video['filename']}")
print(f"Camera: {video['camera_name']}")
print(f"Created: {video['created_at']}")

# Check frames
cursor.execute("SELECT COUNT(*) as count FROM frames WHERE video_id = 28")
total_frames = cursor.fetchone()['count']
print(f"\nTotal frames: {total_frames}")

cursor.execute("SELECT COUNT(*) as count FROM frames WHERE video_id = 28 AND selected_for_training = 1")
training_frames = cursor.fetchone()['count']
print(f"Training frames: {training_frames}")

if total_frames > 0:
    cursor.execute("""
        SELECT id, frame_number, selected_for_training, has_detections 
        FROM frames 
        WHERE video_id = 28 
        ORDER BY frame_number 
        LIMIT 10
    """)
    print(f"\nFirst 10 frames:")
    print(f"{'ID':<8} {'Frame#':<10} {'Training?':<12} {'Detections?':<12}")
    print("-" * 45)
    for row in cursor.fetchall():
        print(f"{row['id']:<8} {row['frame_number']:<10} {row['selected_for_training']:<12} {row['has_detections']:<12}")

# Check detections
cursor.execute("""
    SELECT COUNT(DISTINCT d.id) as detection_count
    FROM frames f
    LEFT JOIN detections d ON f.id = d.frame_id
    WHERE f.video_id = 28
""")
detection_count = cursor.fetchone()['detection_count']
print(f"\nTotal detections: {detection_count}")

conn.close()
