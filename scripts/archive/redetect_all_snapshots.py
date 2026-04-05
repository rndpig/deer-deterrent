#!/usr/bin/env python3
"""
Re-detect all snapshots currently tagged as deer_detected=1.
This will show us what the model actually sees in these images.
"""
import requests
import sys
from collections import defaultdict

API_BASE = "http://192.168.7.215:8000"
ML_DETECTOR = "http://192.168.7.215:8001"

CAMERA_NAMES = {
    "587a624d3fae": "Driveway",
    "10cea9e4511f": "Side"
}

def main():
    print("Fetching all snapshots currently tagged as deer_detected=1...")
    response = requests.get(f"{API_BASE}/api/ring-events", params={
        "deer_detected": "true",
        "limit": 2500
    })
    response.raise_for_status()
    
    tagged_events = response.json()["events"]
    print(f"Found {len(tagged_events)} snapshots to re-detect\n")
    
    # Group by camera
    by_camera = defaultdict(list)
    for event in tagged_events:
        camera_id = event.get("camera_id", "unknown")
        by_camera[camera_id].append(event)
    
    print("Breakdown by camera:")
    for camera_id, events in by_camera.items():
        camera_name = CAMERA_NAMES.get(camera_id, camera_id)
        print(f"  {camera_name}: {len(events)} snapshots")
    print()
    
    # Fetch settings
    settings_resp = requests.get(f"{API_BASE}/api/settings")
    settings_resp.raise_for_status()
    threshold = settings_resp.json().get("confidence_threshold", 0.6)
    print(f"Current threshold: {threshold}\n")
    
    # Re-detect each snapshot
    results = {
        "still_deer": [],
        "false_positive": [],
        "errors": []
    }
    
    count = 0
    for event in tagged_events:
        count += 1
        event_id = event["id"]
        camera_id = event.get("camera_id", "unknown")
        camera_name = CAMERA_NAMES.get(camera_id, camera_id)
        old_confidence = event.get("detection_confidence", 0.0)
        
        try:
            # Get snapshot path and construct URL
            snapshot_path = event.get("snapshot_path")
            if not snapshot_path:
                results["errors"].append({
                    "id": event_id,
                    "camera": camera_name,
                    "reason": "No snapshot path"
                })
                continue
            
            # Download image from backend API
            snapshot_url = f"{API_BASE}/api/ring-snapshots/{event_id}/image"
            img_response = requests.get(snapshot_url)
            img_response.raise_for_status()
            
            # Send to ML detector
            files = {"file": ("snapshot.jpg", img_response.content, "image/jpeg")}
            detect_response = requests.post(f"{ML_DETECTOR}/detect", files=files)
            detect_response.raise_for_status()
            
            detection = detect_response.json()
            new_deer_detected = detection.get("deer_detected", False)
            new_confidence = detection.get("detection_confidence", 0.0)
            detections = detection.get("detections", [])
            
            # Classify result
            if new_deer_detected:
                results["still_deer"].append({
                    "id": event_id,
                    "camera": camera_name,
                    "old_conf": old_confidence,
                    "new_conf": new_confidence,
                    "detections": detections
                })
            else:
                results["false_positive"].append({
                    "id": event_id,
                    "camera": camera_name,
                    "old_conf": old_confidence,
                    "new_conf": new_confidence
                })
                
                # Update database to remove false positive
                patch_response = requests.patch(
                    f"{API_BASE}/api/ring-events/{event_id}",
                    json={"deer_detected": False, "detection_confidence": 0.0}
                )
                patch_response.raise_for_status()
            
            if count % 50 == 0:
                print(f"Progress: {count}/{len(tagged_events)} - "
                      f"Still deer: {len(results['still_deer'])}, "
                      f"False positives: {len(results['false_positive'])}")
                
        except Exception as e:
            results["errors"].append({
                "id": event_id,
                "camera": camera_name,
                "reason": str(e)
            })
    
    # Final report
    print("\n" + "="*70)
    print("RE-DETECTION COMPLETE")
    print("="*70)
    
    print(f"\n✓ Still legitimate deer detections: {len(results['still_deer'])}")
    if results["still_deer"]:
        camera_breakdown = defaultdict(int)
        for r in results["still_deer"]:
            camera_breakdown[r["camera"]] += 1
        for camera, count in camera_breakdown.items():
            print(f"    {camera}: {count}")
    
    print(f"\n✗ False positives (untagged): {len(results['false_positive'])}")
    if results["false_positive"]:
        camera_breakdown = defaultdict(int)
        for r in results["false_positive"]:
            camera_breakdown[r["camera"]] += 1
        for camera, count in camera_breakdown.items():
            print(f"    {camera}: {count}")
    
    if results["errors"]:
        print(f"\n⚠ Errors: {len(results['errors'])}")
    
    # Show sample false positives
    if results["false_positive"]:
        print(f"\nSample false positives (first 10):")
        for fp in results["false_positive"][:10]:
            print(f"  Event {fp['id']} ({fp['camera']}): "
                  f"Old conf={fp['old_conf']:.2f}, New=0.0")
    
    # Show detections that are still marked as deer
    if results["still_deer"]:
        print(f"\nSample confirmed deer (first 10):")
        for sd in results["still_deer"][:10]:
            det_info = ", ".join([f"{d['class']} ({d['confidence']:.2f})" 
                                 for d in sd['detections']])
            print(f"  Event {sd['id']} ({sd['camera']}): "
                  f"Conf={sd['new_conf']:.2f} - {det_info}")

if __name__ == "__main__":
    main()
