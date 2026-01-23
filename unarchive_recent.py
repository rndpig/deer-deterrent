import sys
sys.path.insert(0, '/app')
import database as db
from datetime import datetime, timedelta

db.init_database()

# Unarchive snapshots that should not have been archived (less than 3 days old)
cutoff = (datetime.now() - timedelta(days=3)).isoformat()
print(f"Unarchiving snapshots newer than: {cutoff}")

conn = db.get_connection()
cursor = conn.cursor()

# Find incorrectly archived snapshots
cursor.execute("""
    SELECT id, timestamp FROM ring_events 
    WHERE archived = 1 AND timestamp > ?
""", (cutoff,))

to_unarchive = cursor.fetchall()
print(f"Found {len(to_unarchive)} snapshots to unarchive")

# Unarchive them
cursor.execute("""
    UPDATE ring_events 
    SET archived = 0 
    WHERE archived = 1 AND timestamp > ?
""", (cutoff,))

conn.commit()
print(f"Unarchived {cursor.rowcount} snapshots")

# Check new counts
cursor.execute("SELECT COUNT(*) FROM ring_events WHERE snapshot_path IS NOT NULL AND archived = 0")
print(f"\nNon-archived snapshots: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM ring_events WHERE snapshot_path IS NOT NULL AND archived = 1")
print(f"Archived snapshots: {cursor.fetchone()[0]}")

conn.close()
