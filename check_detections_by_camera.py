import sqlite3

conn = sqlite3.connect('/home/rndpig/deer-deterrent/backend/data/training.db')
cursor = conn.cursor()

# Check remaining deer detections by camera
cursor.execute("""
    SELECT camera_id, COUNT(*) 
    FROM ring_events 
    WHERE deer_detected = 1 
    GROUP BY camera_id
""")

print("\n📊 Remaining deer detections by camera:")
for camera_id, count in cursor.fetchall():
    camera_name = {
        '587a624d3fae': 'Driveway',
        '10cea9e4511f': 'Side',
        '4439c4de7a79': 'Front Door',
        'f045dae9383a': 'Back'
    }.get(camera_id, camera_id)
    print(f"  {camera_name}: {count}")

# Check total
cursor.execute("SELECT COUNT(*) FROM ring_events WHERE deer_detected = 1")
total = cursor.fetchone()[0]
print(f"\n✅ Total deer detections: {total}")

conn.close()
