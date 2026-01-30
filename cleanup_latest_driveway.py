import sqlite3

conn = sqlite3.connect('/home/rndpig/deer-deterrent/backend/data/training.db')
cursor = conn.cursor()

# Remove the most recent Driveway detection (created after cleanup)
cursor.execute("""
    UPDATE ring_events 
    SET deer_detected = 0, detection_confidence = NULL 
    WHERE id = 22099
""")

conn.commit()
print(f"✅ Removed new Driveway false positive (ID: 22099)")

# Show final stats
cursor.execute("""
    SELECT camera_id, COUNT(*) 
    FROM ring_events 
    WHERE deer_detected = 1 
    GROUP BY camera_id
""")

print("\n📊 Final deer detections by camera:")
for camera_id, count in cursor.fetchall():
    camera_name = {
        '587a624d3fae': 'Driveway',
        '10cea9e4511f': 'Side',
        '4439c4de7a79': 'Front Door',
        'f045dae9383a': 'Back'
    }.get(camera_id, camera_id)
    print(f"  {camera_name}: {count}")

cursor.execute("SELECT COUNT(*) FROM ring_events WHERE deer_detected = 1")
total = cursor.fetchone()[0]
print(f"\n✅ Total deer detections: {total}")

conn.close()
