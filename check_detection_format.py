import sys
sys.path.insert(0, '/app')
from database import get_connection
import json

conn = get_connection()
cursor = conn.cursor()

# Get a frame with detections
cursor.execute("""
    SELECT f.id, f.frame_number
    FROM frames f
    JOIN detections d ON f.id = d.frame_id
    WHERE f.video_id = 28
    LIMIT 1
""")
frame = cursor.fetchone()

if frame:
    frame_id = frame[0]
    print(f"Frame {frame[1]} (ID: {frame_id}) has detections:")
    
    cursor.execute("SELECT * FROM detections WHERE frame_id = ?", (frame_id,))
    detections = [dict(row) for row in cursor.fetchall()]
    
    for det in detections:
        print(f"\nDetection ID: {det['id']}")
        print(f"  bbox_x1: {det['bbox_x1']}")
        print(f"  bbox_y1: {det['bbox_y1']}")
        print(f"  bbox_x2: {det['bbox_x2']}")
        print(f"  bbox_y2: {det['bbox_y2']}")
        print(f"  confidence: {det['confidence']}")
        print(f"  class_name: {det['class_name']}")
else:
    print("No frames with detections found")

conn.close()
