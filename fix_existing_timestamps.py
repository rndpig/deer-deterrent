"""Convert existing UTC timestamps to local time (EST = UTC-5)"""
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("data/training.db")
cursor = conn.cursor()

# Get all events
cursor.execute("SELECT id, created_at FROM ring_events WHERE created_at IS NOT NULL")
events = cursor.fetchall()

print(f"Found {len(events)} events to update")

# UTC offset for EST (Eastern Standard Time)
utc_offset = timedelta(hours=-5)

updated = 0
for event_id, created_at in events:
    try:
        # Parse the timestamp (format: "2026-01-10 00:29:40")
        utc_time = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
        
        # Convert to local time (subtract 5 hours)
        local_time = utc_time + utc_offset
        
        # Update the record
        cursor.execute(
            "UPDATE ring_events SET created_at = ? WHERE id = ?",
            (local_time.strftime("%Y-%m-%d %H:%M:%S"), event_id)
        )
        updated += 1
        
        if updated <= 5:  # Show first 5 examples
            print(f"  ID {event_id}: {created_at} → {local_time.strftime('%Y-%m-%d %H:%M:%S')}")
    except Exception as e:
        print(f"  ⚠️ Error updating event {event_id}: {e}")

conn.commit()
conn.close()

print(f"\n✅ Updated {updated} timestamps from UTC to local time (EST)")
