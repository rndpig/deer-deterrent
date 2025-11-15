#!/usr/bin/env python3
"""Test Google Drive API connection."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from services.drive_sync import test_connection

if __name__ == '__main__':
    print("=" * 60)
    print("Testing Google Drive API Connection")
    print("=" * 60)
    print()
    
    success = test_connection()
    
    print()
    print("=" * 60)
    if success:
        print("✓ Connection test passed!")
        print("\nNext steps:")
        print("1. Start labeling detections in the dashboard")
        print("2. Export labeled data")
        print("3. Sync to Google Drive")
    else:
        print("❌ Connection test failed")
        print("\nPlease complete setup:")
        print("1. Follow docs/GOOGLE_DRIVE_SETUP.md")
        print("2. Add credentials to configs/google-credentials.json")
        print("3. Update .env with folder ID")
    print("=" * 60)
    
    sys.exit(0 if success else 1)
