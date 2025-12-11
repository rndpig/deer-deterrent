"""Check frame distribution across videos."""
import sys
sys.path.insert(0, '/home/rndpig/deer-deterrent')

from backend.database import get_connection

conn = get_connection()
cursor = conn.cursor()

print("\n=== FRAME DISTRIBUTION BY VIDEO ===")
cursor.execute("""
    SELECT video_id, COUNT(*) as frame_count
    FROM frames 
    GROUP BY video_id 
    ORDER BY video_id DESC 
    LIMIT 10
""")
print(f"{'Video ID':<10} {'Frame Count':<15}")
print("-" * 25)
for row in cursor.fetchall():
    print(f"{row[0]:<10} {row[1]:<15}")

print("\n=== FRAMES WITH selected_for_training=1 ===")
cursor.execute("""
    SELECT video_id, COUNT(*) as training_count
    FROM frames 
    WHERE selected_for_training = 1
    GROUP BY video_id 
    ORDER BY video_id DESC 
    LIMIT 10
""")
print(f"{'Video ID':<10} {'Training Frames':<15}")
print("-" * 25)
for row in cursor.fetchall():
    print(f"{row[0]:<10} {row[1]:<15}")

conn.close()
