import sys
from pathlib import Path

# Add src to path like backend does
sys.path.insert(0, str(Path.cwd().parent / 'src'))

# Try to import DriveSync
try:
    from services.drive_sync import DriveSync
    print("✓ DriveSync import successful")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    import traceback
    traceback.print_exc()
