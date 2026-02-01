#!/usr/bin/env python3
"""
Populate bbox data for archived deer detections and optionally unarchive them.
"""
import requests
import time

API_URL = "http://192.168.7.215:8000"

# IDs of archived deer detections
ARCHIVED_DEER_IDS = [17365, 17363, 17361, 17359, 5766]

def populate_and_unarchive(event_id):
    """Populate bbox data and unarchive a snapshot."""
    print(f"Processing snapshot {event_id}...")
    
    # Step 1: Populate bbox data
    print(f"  - Running detection...", end=" ")
    try:
        response = requests.post(
            f"{API_URL}/api/ring-snapshots/{event_id}/rerun-detection",
            params={"threshold": 0.15},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✓ {data.get('detection_count', 0)} detections")
        else:
            print(f"✗ Error {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ {str(e)}")
        return False
    
    # Step 2: Unarchive
    print(f"  - Unarchiving...", end=" ")
    try:
        response = requests.post(
            f"{API_URL}/api/ring-snapshots/{event_id}/unarchive",
            timeout=10
        )
        if response.status_code == 200:
            print("✓")
            return True
        else:
            print(f"✗ Error {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ {str(e)}")
        return False

def main():
    print("=" * 60)
    print("Restoring archived deer detections")
    print("=" * 60)
    print(f"\nFound {len(ARCHIVED_DEER_IDS)} archived deer detections")
    print()
    
    success_count = 0
    for event_id in ARCHIVED_DEER_IDS:
        if populate_and_unarchive(event_id):
            success_count += 1
        time.sleep(0.5)
        print()
    
    print("=" * 60)
    print(f"Complete: {success_count}/{len(ARCHIVED_DEER_IDS)} restored")
    print("=" * 60)

if __name__ == "__main__":
    main()
