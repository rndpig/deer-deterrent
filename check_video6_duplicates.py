import sys
sys.path.insert(0, '/app')
from database import get_connection

conn = get_connection()
cursor = conn.cursor()

video_id = 6

cursor.execute("SELECT filename FROM videos WHERE id = ?", (video_id,))
video = cursor.fetchone()
print(f"Video: {video[0]}\n")

# Get frame count
cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = ?", (video_id,))
total = cursor.fetchone()[0]
print(f"Total frames: {total}\n")

# Check for gaps in IDs that suggest two extractions
cursor.execute("""
    SELECT MIN(id), MAX(id), COUNT(*)
    FROM frames
    WHERE video_id = ?
""", (video_id,))
min_id, max_id, count = cursor.fetchone()
print(f"Frame ID range: {min_id} to {max_id} ({count} frames)")

# Look for a gap suggesting duplicate extraction
cursor.execute("""
    SELECT id, frame_number
    FROM frames
    WHERE video_id = ?
    ORDER BY id
""", (video_id,))

frames = cursor.fetchall()
ids = [f[0] for f in frames]

# Check for large gap
for i in range(len(ids)-1):
    gap = ids[i+1] - ids[i]
    if gap > 50:  # Large gap suggests separate extractions
        print(f"\n⚠️  Large ID gap detected: {ids[i]} -> {ids[i+1]} (gap of {gap})")
        print(f"   First batch: IDs {ids[0]} to {ids[i]} ({i+1} frames)")
        print(f"   Second batch: IDs {ids[i+1]} to {ids[-1]} ({len(ids)-i-1} frames)")
        
        # Recommend deletion
        print(f"\n   RECOMMENDATION: Delete frames with ID >= {ids[i+1]}")
        break
else:
    print("\n✓ No large ID gaps found - frames appear to be from single extraction")

conn.close()
