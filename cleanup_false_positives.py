#!/usr/bin/env python3
"""
Clean up false positive detections (deer_detected=1 but confidence=0.0)
caused by bug in animal class filtering before Jan 29 2025 fix.
"""
import requests
import sys

API_BASE = "http://192.168.7.215:8000"

def main():
    print("Fetching false positive records...")
    response = requests.get(f"{API_BASE}/api/ring-events", params={
        "deer_detected": "true",
        "limit": 2500
    })
    response.raise_for_status()
    
    all_events = response.json()["events"]
    false_positives = [e for e in all_events if e["detection_confidence"] == 0.0]
    
    print(f"Found {len(false_positives)} false positives to untag")
    
    if not false_positives:
        print("No false positives found!")
        return
    
    count = 0
    errors = 0
    
    for event in false_positives:
        try:
            response = requests.patch(
                f"{API_BASE}/api/ring-events/{event['id']}",
                json={"deer_detected": False, "detection_confidence": 0.0}
            )
            response.raise_for_status()
            count += 1
            
            if count % 100 == 0:
                print(f"Progress: {count}/{len(false_positives)} untagged...")
                
        except Exception as e:
            errors += 1
            print(f"Error on event {event['id']}: {e}")
            if errors > 10:
                print("Too many errors, stopping")
                sys.exit(1)
    
    print(f"\n✓ Successfully untagged {count} false positives")
    if errors > 0:
        print(f"⚠ {errors} errors occurred")

if __name__ == "__main__":
    main()
