import sys
sys.path.insert(0, '/app')
from database import get_connection

conn = get_connection()
cursor = conn.cursor()

# Check video 4
cursor.execute("SELECT id, filename FROM videos WHERE id = 4")
video = cursor.fetchone()

print(f"Video: {video[1] if video else 'Not found'}")

cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = 4")
total = cursor.fetchone()[0]
print(f"Total frames: {total}")

cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = 4 AND selected_for_training = 1")
training = cursor.fetchone()[0]
print(f"Training frames: {training}")

if total != training:
    print(f"\n⚠️  Mismatch! Fixing...")
    cursor.execute("UPDATE frames SET selected_for_training = 1 WHERE video_id = 4")
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = 4 AND selected_for_training = 1")
    new_count = cursor.fetchone()[0]
    print(f"✓ Fixed! Now {new_count} frames marked for training")

conn.close()
