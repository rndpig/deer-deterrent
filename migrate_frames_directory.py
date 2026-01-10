#!/usr/bin/env python3
"""
Migrate frame files from data/training_frames/ to data/frames/
and update database paths accordingly.

This consolidates all frames into a single directory for simplicity.
"""
import shutil
import sqlite3
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_frames():
    """Move all frames from training_frames to frames and update database."""
    
    old_dir = Path("data/training_frames")
    new_dir = Path("data/frames")
    db_path = Path("data/training.db")
    
    if not old_dir.exists():
        logger.info("No data/training_frames directory found - nothing to migrate")
        return
    
    if not db_path.exists():
        logger.error("Database not found at data/training.db")
        return
    
    # Create new directory
    new_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all frame files
    frame_files = list(old_dir.glob("*.jpg"))
    logger.info(f"Found {len(frame_files)} frame files to migrate")
    
    # Move files
    moved_count = 0
    skipped_count = 0
    
    for old_path in frame_files:
        new_path = new_dir / old_path.name
        
        if new_path.exists():
            logger.debug(f"Skipping {old_path.name} - already exists in destination")
            skipped_count += 1
            continue
        
        try:
            shutil.move(str(old_path), str(new_path))
            moved_count += 1
            if moved_count % 100 == 0:
                logger.info(f"Moved {moved_count} files...")
        except Exception as e:
            logger.error(f"Error moving {old_path.name}: {e}")
    
    logger.info(f"Moved {moved_count} files, skipped {skipped_count} duplicates")
    
    # Update database paths
    logger.info("Updating database image paths...")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Update paths that point to training_frames
    cursor.execute("""
        UPDATE frames 
        SET image_path = REPLACE(image_path, 'data/training_frames/', 'data/frames/')
        WHERE image_path LIKE 'data/training_frames/%'
    """)
    
    updated_rows = cursor.rowcount
    logger.info(f"Updated {updated_rows} database records")
    
    conn.commit()
    conn.close()
    
    # Check if old directory is empty
    remaining_files = list(old_dir.glob("*"))
    if remaining_files:
        logger.warning(f"{len(remaining_files)} files remain in {old_dir}")
        logger.info("Review remaining files before deleting the old directory")
    else:
        logger.info(f"Old directory {old_dir} is empty and can be safely deleted")
        logger.info(f"Run: rm -rf {old_dir}")
    
    logger.info("Migration complete!")

if __name__ == "__main__":
    migrate_frames()
