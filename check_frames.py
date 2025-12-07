#!/usr/bin/env python3
from backend.database import get_connection

conn = get_connection()

# Check frames for video 4
result = conn.execute("""
    SELECT COUNT(*) as cnt, selected_for_training 
    FROM frames 
    WHERE video_id=4 
    GROUP BY selected_for_training
""").fetchall()

print("Video 4 frames by training flag:")
for row in result:
    print(f"  Count: {row[0]}, selected_for_training: {row[1]}")

# Check total
total = conn.execute("SELECT COUNT(*) FROM frames WHERE video_id=4").fetchone()[0]
print(f"\nTotal frames for video 4: {total}")
