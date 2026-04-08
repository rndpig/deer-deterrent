#!/usr/bin/env python3
"""Migrate snapshots to unified storage and normalize database paths.

This script:
1. Moves files from backend/data/snapshots/ to dell-deployment/data/snapshots/
2. Updates database paths from 'data/snapshots/' to 'snapshots/'
"""
import sqlite3
import shutil
from pathlib import Path

DB_PATH = "/home/rndpig/deer-deterrent/backend/data/training.db"
OLD_DIR = Path("/home/rndpig/deer-deterrent/backend/data/snapshots")
NEW_DIR = Path("/home/rndpig/deer-deterrent/dell-deployment/data/snapshots")

def migrate_files():
    """Move files from old location to new location."""
    if not OLD_DIR.exists():
        print(f"Old directory doesn't exist: {OLD_DIR}")
        return 0
    
    moved = 0
    skipped = 0
    
    for src_file in OLD_DIR.glob("*.jpg"):
        dst_file = NEW_DIR / src_file.name
        
        if dst_file.exists():
            # File already exists in destination
            if src_file.stat().st_size == dst_file.stat().st_size:
                # Same size, safe to remove source
                src_file.unlink()
                skipped += 1
            else:
                print(f"  Conflict (different size): {src_file.name}")
        else:
            # Move file
            shutil.move(str(src_file), str(dst_file))
            moved += 1
    
    print(f"Files moved: {moved}, duplicates removed: {skipped}")
    return moved

def update_database_paths():
    """Update database paths from 'data/snapshots/' to 'snapshots/'."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Count records to update
    cursor.execute("""
        SELECT COUNT(*) FROM ring_events 
        WHERE snapshot_path LIKE 'data/snapshots/%'
    """)
    count = cursor.fetchone()[0]
    print(f"Database records to update: {count}")
    
    if count > 0:
        # Update paths
        cursor.execute("""
            UPDATE ring_events 
            SET snapshot_path = REPLACE(snapshot_path, 'data/snapshots/', 'snapshots/')
            WHERE snapshot_path LIKE 'data/snapshots/%'
        """)
        conn.commit()
        print(f"Updated {cursor.rowcount} database records")
    
    # Verify
    cursor.execute("""
        SELECT snapshot_path, COUNT(*) as cnt 
        FROM ring_events 
        WHERE snapshot_path IS NOT NULL
        GROUP BY SUBSTR(snapshot_path, 1, INSTR(snapshot_path, '/'))
        ORDER BY cnt DESC
    """)
    print("\nPath prefixes in database:")
    for row in cursor.fetchall():
        print(f"  {row[0][:30]}... : {row[1]} records")
    
    conn.close()
    return count

if __name__ == "__main__":
    print("=== Snapshot Migration ===\n")
    
    print("Step 1: Moving files...")
    migrate_files()
    
    print("\nStep 2: Updating database paths...")
    update_database_paths()
    
    print("\n=== Migration Complete ===")
