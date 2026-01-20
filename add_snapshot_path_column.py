import sqlite3

conn = sqlite3.connect("/app/data/training.db")
cursor = conn.cursor()

# Check if snapshot_path column exists
cursor.execute("PRAGMA table_info(ring_events)")
columns = [row[1] for row in cursor.fetchall()]

if 'snapshot_path' not in columns:
    print("Adding snapshot_path column to ring_events table...")
    cursor.execute("ALTER TABLE ring_events ADD COLUMN snapshot_path TEXT")
    conn.commit()
    print("✓ Column added successfully")
else:
    print("snapshot_path column already exists")

# Verify
cursor.execute("PRAGMA table_info(ring_events)")
print("\nCurrent ring_events schema:")
for row in cursor.fetchall():
    print(f"  {row[1]} ({row[2]})")

conn.close()
