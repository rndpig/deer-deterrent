import sys
sys.path.insert(0, '/app')
import database as db

db.init_database()

# Update the manual upload path
conn = db.get_connection()
cursor = conn.cursor()

cursor.execute("""
    UPDATE ring_events 
    SET snapshot_path = 'data/snapshots/manual_upload_20260122_203532.jpg'
    WHERE id = 5666
""")

conn.commit()
print(f"Updated {cursor.rowcount} rows")

# Verify
cursor.execute("SELECT id, snapshot_path FROM ring_events WHERE id = 5666")
row = cursor.fetchone()
if row:
    print(f"Event {row[0]}: {row[1]}")

conn.close()
