"""Migrate ring_events table to use local time for created_at"""
import sqlite3
from pathlib import Path

DB_PATH = Path("data/training.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check current schema
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ring_events'")
    current_schema = cursor.fetchone()[0]
    print(f"Current schema:\n{current_schema}\n")
    
    if "CURRENT_TIMESTAMP" in current_schema:
        print("❌ Table still uses CURRENT_TIMESTAMP - needs migration")
        
        # Rename old table
        cursor.execute("ALTER TABLE ring_events RENAME TO ring_events_old")
        
        # Create new table with correct DEFAULT
        cursor.execute("""
            CREATE TABLE ring_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                snapshot_available BOOLEAN DEFAULT 0,
                snapshot_size INTEGER,
                recording_url TEXT,
                processed BOOLEAN DEFAULT 0,
                deer_detected BOOLEAN,
                detection_confidence REAL,
                error_message TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            )
        """)
        
        # Copy data from old table
        cursor.execute("""
            INSERT INTO ring_events (id, camera_id, event_type, timestamp, snapshot_available,
                                    snapshot_size, recording_url, processed, deer_detected,
                                    detection_confidence, error_message, created_at)
            SELECT id, camera_id, event_type, timestamp, snapshot_available,
                   snapshot_size, recording_url, processed, deer_detected,
                   detection_confidence, error_message, created_at
            FROM ring_events_old
        """)
        
        # Recreate indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ring_events_camera ON ring_events(camera_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ring_events_timestamp ON ring_events(timestamp)")
        
        # Drop old table
        cursor.execute("DROP TABLE ring_events_old")
        
        conn.commit()
        
        # Verify new schema
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ring_events'")
        new_schema = cursor.fetchone()[0]
        print(f"\n✅ Migration complete! New schema:\n{new_schema}")
        
        # Count records
        cursor.execute("SELECT COUNT(*) FROM ring_events")
        count = cursor.fetchone()[0]
        print(f"\n📊 Migrated {count} events")
        
    else:
        print("✅ Table already uses localtime - no migration needed")
    
    conn.close()

if __name__ == "__main__":
    migrate()
