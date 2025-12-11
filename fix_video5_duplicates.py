import sys
sys.path.insert(0, '/app')
from database import get_connection

conn = get_connection()
cursor = conn.cursor()

video_id = 5

print("Deleting duplicate frames (IDs 2059-2103) from video 5...")
print("Keeping original frames (IDs 1924-1971) with auto-detections\n")

# Delete frames with IDs >= 2059 for video 5
cursor.execute("""
    DELETE FROM frames 
    WHERE video_id = ? AND id >= 2059
""", (video_id,))

deleted_count = cursor.rowcount

conn.commit()

# Verify
cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = ?", (video_id,))
remaining = cursor.fetchone()[0]

print(f"✓ Deleted {deleted_count} duplicate frames")
print(f"✓ Remaining frames: {remaining}")

conn.close()
