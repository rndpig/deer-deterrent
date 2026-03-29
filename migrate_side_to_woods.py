#!/usr/bin/env python3
"""
Migrate old Side camera snapshots (10cea9e4511f) to new Side camera ID (c4dbad08f862).

The physical camera 10cea9e4511f was moved from the Side position to the barn (renamed "Woods").
A new camera c4dbad08f862 now occupies the Side position. All historical snapshots from the
Side location should be attributed to the new Side camera ID.

Steps:
1. Back up database
2. Show current state
3. Update ring_events.camera_id: 10cea9e4511f -> c4dbad08f862
4. Update ring_events.snapshot_path: replace 10cea9e4511f with c4dbad08f862 in filenames
5. Rename snapshot files on disk
6. Check videos.camera_name
7. Verify results
"""

import sqlite3
import shutil
import os
import re
from pathlib import Path
from datetime import datetime

DB_PATH = "/home/rndpig/deer-deterrent/backend/data/training.db"
SNAPSHOT_DIR = "/home/rndpig/deer-deterrent/dell-deployment/data/snapshots"
OLD_ID = "10cea9e4511f"
NEW_ID = "c4dbad08f862"

def main():
    # Step 1: Back up database
    backup_path = DB_PATH + f".backup_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"=== Step 1: Backing up database ===")
    print(f"  Source: {DB_PATH}")
    print(f"  Backup: {backup_path}")
    shutil.copy2(DB_PATH, backup_path)
    print(f"  Backup created successfully ({os.path.getsize(backup_path)} bytes)")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Step 2: Show current state
    print(f"\n=== Step 2: Current state ===")
    cur.execute("SELECT camera_id, COUNT(*) as count FROM ring_events GROUP BY camera_id ORDER BY count DESC")
    print("  ring_events by camera_id:")
    for row in cur.fetchall():
        print(f"    {row['camera_id']}: {row['count']} events")

    cur.execute("SELECT COUNT(*) as count FROM ring_events WHERE camera_id = ? AND snapshot_path IS NOT NULL", (OLD_ID,))
    snap_count = cur.fetchone()['count']
    print(f"\n  Events with {OLD_ID} that have snapshot_path: {snap_count}")

    cur.execute("SELECT COUNT(*) as count FROM ring_events WHERE camera_id = ? AND deer_detected = 1", (OLD_ID,))
    deer_count = cur.fetchone()['count']
    print(f"  Events with {OLD_ID} that have deer_detected: {deer_count}")

    cur.execute("SELECT COUNT(*) as count FROM ring_events WHERE camera_id = ? AND snapshot_path LIKE ?", (OLD_ID, f"%{OLD_ID}%"))
    path_count = cur.fetchone()['count']
    print(f"  Events with {OLD_ID} in snapshot_path: {path_count}")

    # Check videos table
    cur.execute("SELECT camera_name, COUNT(*) as count FROM videos WHERE camera_name = ?", (OLD_ID,))
    video_rows = cur.fetchall()
    video_count = sum(r['count'] for r in video_rows)
    print(f"  Videos with camera_name={OLD_ID}: {video_count}")

    # Step 3: Update ring_events.camera_id
    print(f"\n=== Step 3: Updating ring_events.camera_id ===")
    cur.execute("UPDATE ring_events SET camera_id = ? WHERE camera_id = ?", (NEW_ID, OLD_ID))
    updated_camera = cur.rowcount
    print(f"  Updated {updated_camera} rows: camera_id {OLD_ID} -> {NEW_ID}")

    # Step 4: Update ring_events.snapshot_path
    print(f"\n=== Step 4: Updating ring_events.snapshot_path ===")
    cur.execute(
        "UPDATE ring_events SET snapshot_path = REPLACE(snapshot_path, ?, ?) WHERE snapshot_path LIKE ?",
        (OLD_ID, NEW_ID, f"%{OLD_ID}%")
    )
    updated_path = cur.rowcount
    print(f"  Updated {updated_path} rows: snapshot_path filenames {OLD_ID} -> {NEW_ID}")

    conn.commit()
    print("  Database changes committed.")

    # Step 5: Rename snapshot files on disk
    print(f"\n=== Step 5: Renaming snapshot files on disk ===")
    snapshot_dir = Path(SNAPSHOT_DIR)
    if snapshot_dir.exists():
        renamed = 0
        errors = 0
        for f in sorted(snapshot_dir.glob(f"*{OLD_ID}*")):
            new_name = f.name.replace(OLD_ID, NEW_ID)
            new_path = f.parent / new_name
            try:
                f.rename(new_path)
                renamed += 1
            except Exception as e:
                print(f"  ERROR renaming {f.name}: {e}")
                errors += 1
        print(f"  Renamed {renamed} files, {errors} errors")
    else:
        print(f"  WARNING: Snapshot directory not found: {SNAPSHOT_DIR}")

    # Step 6: Update videos.camera_name  
    print(f"\n=== Step 6: Updating videos.camera_name ===")
    if video_count > 0:
        cur.execute("UPDATE videos SET camera_name = ? WHERE camera_name = ?", (NEW_ID, OLD_ID))
        updated_videos = cur.rowcount
        conn.commit()
        print(f"  Updated {updated_videos} video rows: camera_name {OLD_ID} -> {NEW_ID}")
    else:
        print(f"  No videos to update")

    # Step 7: Verify results
    print(f"\n=== Step 7: Verification ===")
    cur.execute("SELECT camera_id, COUNT(*) as count FROM ring_events GROUP BY camera_id ORDER BY count DESC")
    print("  ring_events by camera_id (after migration):")
    for row in cur.fetchall():
        print(f"    {row['camera_id']}: {row['count']} events")

    cur.execute("SELECT COUNT(*) FROM ring_events WHERE camera_id = ?", (OLD_ID,))
    remaining = cur.fetchone()[0]
    print(f"\n  Remaining events with old ID {OLD_ID}: {remaining}")

    cur.execute("SELECT COUNT(*) FROM ring_events WHERE snapshot_path LIKE ?", (f"%{OLD_ID}%",))
    remaining_paths = cur.fetchone()[0]
    print(f"  Remaining snapshot_paths with old ID: {remaining_paths}")

    if snapshot_dir.exists():
        remaining_files = list(snapshot_dir.glob(f"*{OLD_ID}*"))
        print(f"  Remaining files with old ID on disk: {len(remaining_files)}")
    
    cur.execute("SELECT COUNT(*) FROM videos WHERE camera_name = ?", (OLD_ID,))
    remaining_videos = cur.fetchone()[0]
    print(f"  Remaining videos with old ID: {remaining_videos}")

    if remaining == 0 and remaining_paths == 0 and remaining_videos == 0:
        print(f"\n  ✓ Migration complete! All references to {OLD_ID} have been updated to {NEW_ID}")
    else:
        print(f"\n  ⚠ Some references to {OLD_ID} remain - check above for details")

    conn.close()
    print(f"\n  Database backup at: {backup_path}")

if __name__ == "__main__":
    main()
