#!/usr/bin/env python3
"""
Populate bbox data for existing Ring snapshot detections.
Run this to backfill detection_bboxes for snapshots that have deer_detected=1.
"""
import requests
import time

API_URL = "http://192.168.7.215:8000"

def populate_bbox_for_snapshot(event_id):
    """Re-run detection to populate bbox data for a snapshot."""
    print(f"Processing snapshot {event_id}...", end=" ")
    try:
        response = requests.post(
            f"{API_URL}/api/ring-snapshots/{event_id}/rerun-detection",
            params={"threshold": 0.15},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✓ {data.get('detection_count', 0)} detections")
            return True
        else:
            print(f"✗ Error {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ {str(e)}")
        return False

def main():
    print("=" * 60)
    print("Populating bbox data for existing deer detections")
    print("=" * 60)
    print()
    
    # Get all deer detections
    print("Fetching deer detection snapshots...")
    response = requests.get(f"{API_URL}/api/ring-snapshots", params={"limit": 500, "with_deer": True})
    
    if response.status_code != 200:
        print(f"Error fetching snapshots: {response.status_code}")
        return
    
    snapshots = response.json().get("snapshots", [])
    print(f"Found {len(snapshots)} deer detection snapshots")
    print()
    
    # Process each snapshot
    success_count = 0
    for snapshot in snapshots:
        event_id = snapshot.get("id")
        if event_id:
            if populate_bbox_for_snapshot(event_id):
                success_count += 1
            time.sleep(0.5)  # Small delay to avoid overwhelming the API
    
    print()
    print("=" * 60)
    print(f"Complete: {success_count}/{len(snapshots)} snapshots processed")
    print("=" * 60)

if __name__ == "__main__":
    main()
