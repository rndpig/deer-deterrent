import sqlite3
from datetime import datetime

conn = sqlite3.connect('/home/rndpig/deer-deterrent/backend/data/training.db')
cursor = conn.cursor()

# Check the remaining Driveway detection
cursor.execute("""
    SELECT id, timestamp, detection_confidence, created_at
    FROM ring_events 
    WHERE camera_id = '587a624d3fae' AND deer_detected = 1
    ORDER BY timestamp DESC
""")

print("\n🔍 Remaining Driveway detection:")
for row in cursor.fetchall():
    id, timestamp, confidence, created_at = row
    print(f"  ID: {id}")
    print(f"  Timestamp: {timestamp}")
    print(f"  Confidence: {confidence}")
    print(f"  Created: {created_at}")

# Also check recent Side detections
print("\n\n📸 Recent Side camera detections:")
cursor.execute("""
    SELECT id, timestamp, detection_confidence
    FROM ring_events 
    WHERE camera_id = '10cea9e4511f' AND deer_detected = 1
    ORDER BY timestamp DESC
    LIMIT 5
""")

for row in cursor.fetchall():
    id, timestamp, confidence = row
    print(f"  ID {id}: {timestamp} (confidence: {confidence})")

conn.close()
