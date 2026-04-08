#!/usr/bin/env python3
"""Import snapshots from filesystem that are missing from database."""
import sqlite3
import os
import re
from datetime import datetime
from pathlib import Path

DB_PATH = "/home/rndpig/deer-deterrent/backend/data/training.db"
SNAPSHOT_DIRS = [
    "/home/rndpig/deer-deterrent/dell-deployment/data/snapshots",
    "/home/rndpig/deer-deterrent/backend/data/snapshots"
]

# Camera ID mapping
CAMERA_IDS = {
    '587a624d3fae': 'Driveway',
    '4439c4de7a79': 'Front Door', 
    'f045dae9383a': 'Back',
    '10cea9e4511f': 'Woods',
    'c4dbad08f862': 'Side'
}

def parse_snapshot_filename(filename):
    """Extract timestamp and camera_id from snapshot filename."""
    # Patterns:
    # 20260407_211824_587a624d3fae.jpg
    # event_20260407_211824_587a624d3fae_snapshot.jpg
    # periodic_20260405_022144_c4dbad08f862.jpg
    
    patterns = [
        r'^(\d{8})_(\d{6})_([a-f0-9]+)\.jpg$',
        r'^event_(\d{8})_(\d{6})_([a-f0-9]+)_snapshot\.jpg$',
        r'^periodic_(\d{8})_(\d{6})_([a-f0-9]+)\.jpg$',
    ]
    
    for pattern in patterns:
        match = re.match(pattern, filename)
        if match:
            date_str, time_str, camera_id = match.groups()
            try:
                timestamp = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                return timestamp, camera_id
            except ValueError:
                continue
    return None, None

def get_existing_paths(conn):
    """Get all snapshot paths already in database."""
    cursor = conn.cursor()
    cursor.execute("SELECT snapshot_path FROM ring_events WHERE snapshot_path IS NOT NULL")
    paths = set()
    for row in cursor.fetchall():
        if row[0]:
            # Normalize to just filename for comparison
            paths.add(Path(row[0]).name)
    return paths

def import_snapshots(dry_run=True):
    """Import missing snapshots into database."""
    conn = sqlite3.connect(DB_PATH)
    existing_paths = get_existing_paths(conn)
    print(f"Found {len(existing_paths)} existing snapshot paths in database")
    
    cursor = conn.cursor()
    imported = 0
    skipped = 0
    errors = 0
    
    for snapshot_dir in SNAPSHOT_DIRS:
        if not os.path.exists(snapshot_dir):
            print(f"Directory not found: {snapshot_dir}")
            continue
            
        print(f"\nScanning: {snapshot_dir}")
        
        for filename in os.listdir(snapshot_dir):
            if not filename.endswith('.jpg'):
                continue
                
            # Skip if already in database
            if filename in existing_paths:
                skipped += 1
                continue
            
            # Also check event_ variant
            if filename.startswith('20'):
                event_name = f"event_{filename[:-4]}_snapshot.jpg"
                if event_name in existing_paths:
                    skipped += 1
                    continue
            
            timestamp, camera_id = parse_snapshot_filename(filename)
            if not timestamp or not camera_id:
                print(f"  Could not parse: {filename}")
                errors += 1
                continue
            
            # Determine event type from filename
            if filename.startswith('periodic_'):
                event_type = 'periodic_snapshot'
            elif filename.startswith('event_') or filename.startswith('20'):
                event_type = 'motion'
            else:
                event_type = 'motion'
            
            # Build relative path for database
            if 'dell-deployment' in snapshot_dir:
                rel_path = f"snapshots/{filename}"
            else:
                rel_path = f"data/snapshots/{filename}"
            
            if dry_run:
                print(f"  Would import: {filename} -> {timestamp.isoformat()} | {camera_id}")
            else:
                try:
                    cursor.execute("""
                        INSERT INTO ring_events 
                        (camera_id, event_type, timestamp, snapshot_path, snapshot_available, archived, deer_detected, processed)
                        VALUES (?, ?, ?, ?, 1, 0, NULL, 0)
                    """, (camera_id, event_type, timestamp.isoformat(), rel_path))
                    print(f"  Imported: {filename}")
                except sqlite3.IntegrityError as e:
                    print(f"  Error importing {filename}: {e}")
                    errors += 1
                    continue
            
            imported += 1
    
    if not dry_run:
        conn.commit()
    
    conn.close()
    
    print(f"\n{'DRY RUN - ' if dry_run else ''}Summary:")
    print(f"  Imported: {imported}")
    print(f"  Skipped (already in DB): {skipped}")
    print(f"  Errors: {errors}")
    
    return imported

if __name__ == "__main__":
    import sys
    dry_run = "--execute" not in sys.argv
    
    if dry_run:
        print("=== DRY RUN MODE ===")
        print("Run with --execute to actually import\n")
    else:
        print("=== EXECUTING IMPORT ===\n")
    
    import_snapshots(dry_run=dry_run)
