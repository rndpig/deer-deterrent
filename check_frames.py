#!/usr/bin/env python3
from backend.database import get_connection

conn = get_connection()

# Get all videos
videos = conn.execute("SELECT id, filename FROM videos ORDER BY id").fetchall()

print("=== ALL VIDEOS AND THEIR ACTUAL FRAME COUNTS ===\n")

for video in videos:
    vid, filename = video
    total_frames = conn.execute("SELECT COUNT(*) FROM frames WHERE video_id=?", (vid,)).fetchone()[0]
    training_frames = conn.execute("SELECT COUNT(*) FROM frames WHERE video_id=? AND selected_for_training=1", (vid,)).fetchone()[0]
    
    print(f"Video {vid}: {filename}")
    print(f"  Total frames in DB: {total_frames}")
    print(f"  Training frames: {training_frames}")
    print()

# Check total across all videos
total_all = conn.execute("SELECT COUNT(*) FROM frames").fetchone()[0]
training_all = conn.execute("SELECT COUNT(*) FROM frames WHERE selected_for_training=1").fetchone()[0]

print(f"=== TOTALS ===")
print(f"Total frames (all videos): {total_all}")
print(f"Training frames (all videos): {training_all}")

