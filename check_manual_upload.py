import sys
sys.path.insert(0, '/app')
import database as db
import json

db.init_database()

# Get manual upload
conn = db.get_connection()
cursor = conn.cursor()
cursor.execute("SELECT * FROM ring_events WHERE camera_id = 'manual_upload' ORDER BY id DESC LIMIT 1")
row = cursor.fetchone()
if row:
    event = dict(row)
    print("Manual upload event:")
    print(json.dumps(event, indent=2))
else:
    print("No manual upload found")
conn.close()
