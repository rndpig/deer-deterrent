import sqlite3

conn = sqlite3.connect('/home/rndpig/deer-deterrent/backend/data/training.db')
cursor = conn.cursor()

# Clean up ALL remaining Driveway detections
cursor.execute("""
    SELECT id, timestamp, detection_confidence
    FROM ring_events 
    WHERE camera_id = '587a624d3fae' AND deer_detected = 1
    ORDER BY timestamp DESC
""")

rows = cursor.fetchall()
print(f"\n🔍 Found {len(rows)} Driveway detections to clean:")
for id, timestamp, confidence in rows:
    print(f"  ID {id}: {timestamp} (confidence: {confidence})")

if rows:
    cursor.execute("""
        UPDATE ring_events 
        SET deer_detected = 0, detection_confidence = NULL 
        WHERE camera_id = '587a624d3fae' AND deer_detected = 1
    """)
    conn.commit()
    print(f"\n✅ Cleaned up {cursor.rowcount} Driveway false positives")
else:
    print("\n✅ No Driveway false positives to clean")

# Show final stats
cursor.execute("""
    SELECT camera_id, COUNT(*) 
    FROM ring_events 
    WHERE deer_detected = 1 
    GROUP BY camera_id
""")

print("\n📊 Final deer detections by camera:")
total = 0
for camera_id, count in cursor.fetchall():
    camera_name = {
        '587a624d3fae': 'Driveway',
        '10cea9e4511f': 'Side',
        '4439c4de7a79': 'Front Door',
        'f045dae9383a': 'Back'
    }.get(camera_id, camera_id)
    print(f"  {camera_name}: {count}")
    total += count

print(f"\n✅ Total deer detections: {total}")

conn.close()
