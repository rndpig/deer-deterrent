import sqlite3

conn = sqlite3.connect('/home/rndpig/deer-deterrent/backend/data/training.db')
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM ring_events WHERE camera_id = '587a624d3fae' AND deer_detected = 1")
count = cursor.fetchone()[0]
print(f"Driveway false positives to clean: {count}")

if count > 0:
    cursor.execute("UPDATE ring_events SET deer_detected = 0, detection_confidence = NULL WHERE camera_id = '587a624d3fae' AND deer_detected = 1")
    conn.commit()
    print(f"✅ Cleaned up {cursor.rowcount} Driveway false positives")
else:
    print("✅ No Driveway false positives found")

conn.close()
