"""
Migration script to add snapshot_path column to ring_events table.
Run this once to update the database schema.
"""
import sqlite3
from pathlib import Path

def migrate_database(db_path: str = "data/training.db"):
    """Add snapshot_path column to ring_events table if it doesn't exist."""
    
    db_file = Path(db_path)
    if not db_file.exists():
        print(f"❌ Database not found at {db_path}")
        print("   Database will be created with new schema when backend starts")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if ring_events table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ring_events'")
    if not cursor.fetchone():
        print("✓ ring_events table doesn't exist yet, will be created with new schema")
        conn.close()
        return
    
    # Check if snapshot_path column exists
    cursor.execute("PRAGMA table_info(ring_events)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'snapshot_path' in columns:
        print("✓ snapshot_path column already exists")
        conn.close()
        return
    
    # Add snapshot_path column
    try:
        cursor.execute("ALTER TABLE ring_events ADD COLUMN snapshot_path TEXT")
        conn.commit()
        print("✓ Successfully added snapshot_path column to ring_events table")
    except Exception as e:
        print(f"❌ Failed to add column: {e}")
        conn.rollback()
    
    conn.close()

if __name__ == "__main__":
    print("=" * 80)
    print("DATABASE MIGRATION: Add snapshot_path column")
    print("=" * 80)
    print()
    
    # Migrate local database
    print("Migrating local database...")
    migrate_database("data/training.db")
    
    # Migrate Docker database (if accessible)
    print("\nTo migrate Docker database, run:")
    print("  docker exec deer-backend python /app/migrate_snapshot_path.py")
    
    print("\n" + "=" * 80)
    print("Migration complete!")
    print("=" * 80)
