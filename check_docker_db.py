import sys
sys.path.insert(0, '/app')
from database import DB_PATH, get_connection

print(f"DB Path: {DB_PATH}")
print(f"DB Exists: {DB_PATH.exists()}")

conn = get_connection()
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = 28")
total = cursor.fetchone()[0]
print(f"\nFrames for video 28: {total}")

cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = 28 AND selected_for_training = 1")
training = cursor.fetchone()[0]
print(f"Training frames: {training}")

if total > 0:
    print("\nFirst 5 frames:")
    cursor.execute("""
        SELECT id, frame_number, selected_for_training 
        FROM frames 
        WHERE video_id = 28 
        ORDER BY frame_number 
        LIMIT 5
    """)
    for row in cursor.fetchall():
        print(f"  Frame {row[1]}: selected_for_training={row[2]}")

conn.close()
