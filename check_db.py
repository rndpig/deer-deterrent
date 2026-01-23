import sys
sys.path.insert(0, '/app')
import database as db
import json
from datetime import datetime, timedelta

db.init_database()

# Check counts
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM ring_events WHERE snapshot_path IS NOT NULL AND archived = 0")
print(f"Non-archived snapshots: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM ring_events WHERE snapshot_path IS NOT NULL AND archived = 1")
print(f"Archived snapshots: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM ring_events WHERE camera_id = 'manual_upload'")
print(f"Manual uploads: {cursor.fetchone()[0]}")

# Check timestamps
cutoff = (datetime.now() - timedelta(days=3)).isoformat()
print(f"\nCutoff for 3-day archive: {cutoff}")
print(f"Current time: {datetime.now().isoformat()}")

# Get some recent snapshots
cursor.execute("SELECT timestamp, camera_id, archived FROM ring_events WHERE snapshot_path IS NOT NULL ORDER BY timestamp DESC LIMIT 10")
print("\nMost recent 10 snapshots:")
for row in cursor.fetchall():
    print(f"  {row[0]} - {row[1]} - Archived: {row[2]}")

conn.close()

