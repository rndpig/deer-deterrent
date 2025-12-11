import sys
sys.path.insert(0, '/app')
from database import get_connection

conn = get_connection()
cursor = conn.cursor()

print("Updating all frames for video 28 to selected_for_training=1...")

cursor.execute("UPDATE frames SET selected_for_training = 1 WHERE video_id = 28")
conn.commit()

cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = 28 AND selected_for_training = 1")
count = cursor.fetchone()[0]

print(f"✓ Done! {count} frames now marked for training")

conn.close()
