#!/usr/bin/env python3
"""
Backup the training database before running the training pipeline.
"""
import shutil
from pathlib import Path
from datetime import datetime

def backup_database():
    """Create a timestamped backup of the training database."""
    db_path = Path("data/training.db")
    
    if not db_path.exists():
        print("❌ Database not found at data/training.db")
        return False
    
    # Create backup directory
    backup_dir = Path("data/backups")
    backup_dir.mkdir(exist_ok=True)
    
    # Create timestamped backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"training_backup_{timestamp}.db"
    
    # Copy database
    shutil.copy2(db_path, backup_path)
    
    # Get file sizes
    original_size = db_path.stat().st_size / 1024 / 1024  # MB
    backup_size = backup_path.stat().st_size / 1024 / 1024  # MB
    
    print(f"✅ Database backed up successfully!")
    print(f"   Original: {db_path} ({original_size:.2f} MB)")
    print(f"   Backup:   {backup_path} ({backup_size:.2f} MB)")
    print(f"\n   To restore: copy this backup file back to data/training.db")
    
    return True

if __name__ == "__main__":
    backup_database()
