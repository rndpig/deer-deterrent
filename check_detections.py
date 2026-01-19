import sqlite3

conn = sqlite3.connect("/app/data/training.db")
cursor = conn.cursor()

# Get detections for frames with video_id 32
cursor.execute("""
    SELECT d.class_name, d.confidence, f.frame_number
    FROM detections d
    JOIN frames f ON d.frame_id = f.id
    WHERE f.video_id = 32
    LIMIT 10
""")

results = cursor.fetchall()
conn.close()

print("Detections for video 32:")
for class_name, confidence, frame_num in results:
    print(f"  Frame {frame_num}: {class_name} ({confidence:.2f})")
