import sqlite3

conn = sqlite3.connect("/app/data/training.db")
cursor = conn.cursor()

cursor.execute("SELECT id, camera_id, timestamp, snapshot_path FROM ring_events ORDER BY timestamp DESC LIMIT 10")

print("Recent ring_events:")
for row in cursor.fetchall():
    print(f"  ID {row[0]}: {row[1]} at {row[2]} - snapshot: {row[3]}")

conn.close()
