import sqlite3

conn = sqlite3.connect("/app/data/training.db")
cursor = conn.cursor()

# Delete detections for frames belonging to video 32
cursor.execute("""
    DELETE FROM detections 
    WHERE frame_id IN (
        SELECT id FROM frames WHERE video_id = 32
    )
""")
deleted_detections = cursor.rowcount

# Delete frames for video 32
cursor.execute("DELETE FROM frames WHERE video_id = 32")
deleted_frames = cursor.rowcount

# Update video status to trigger re-analysis
cursor.execute("UPDATE videos SET status = 'pending' WHERE id = 32")

conn.commit()
conn.close()

print(f"Deleted {deleted_detections} detections and {deleted_frames} frames for video 32")
print("Video 32 status set to pending for re-analysis")
