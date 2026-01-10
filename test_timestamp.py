"""Test that new events get local time timestamps"""
import sqlite3
import datetime

conn = sqlite3.connect("data/training.db")
cursor = conn.cursor()

# Insert a test event
now = datetime.datetime.now()
cursor.execute("""
    INSERT INTO ring_events (camera_id, event_type, timestamp)
    VALUES (?, ?, ?)
""", ("test_camera", "test_event", now.isoformat()))
conn.commit()

# Get the last event
cursor.execute("SELECT id, timestamp, created_at FROM ring_events ORDER BY id DESC LIMIT 1")
row = cursor.fetchone()

print(f"Test event inserted:")
print(f"  ID: {row[0]}")
print(f"  timestamp: {row[1]}")
print(f"  created_at: {row[2]}")
print(f"  System time: {now.strftime('%Y-%m-%d %H:%M:%S')}")

# Delete the test event
cursor.execute("DELETE FROM ring_events WHERE camera_id = 'test_camera'")
conn.commit()
print(f"\n✅ Test event deleted")

conn.close()
