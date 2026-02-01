#!/usr/bin/env python3
"""
Test re-detection on a single snapshot to debug.
"""
import requests

API_BASE = "http://192.168.7.215:8000"
ML_DETECTOR = "http://192.168.7.215:8001"

# Get one tagged event
print("Fetching one tagged snapshot...")
response = requests.get(f"{API_BASE}/api/ring-events", params={
    "deer_detected": "true",
    "limit": 1
})
response.raise_for_status()

event = response.json()["events"][0]
event_id = event["id"]
print(f"Event ID: {event_id}")
print(f"Camera: {event.get('camera_id')}")
print(f"Old confidence: {event.get('detection_confidence')}")
print(f"Snapshot path: {event.get('snapshot_path')}")

# Try to get image
print(f"\nFetching image...")
snapshot_url = f"{API_BASE}/api/ring-snapshots/{event_id}/image"
print(f"URL: {snapshot_url}")

try:
    img_response = requests.get(snapshot_url)
    print(f"Status code: {img_response.status_code}")
    print(f"Content length: {len(img_response.content)}")
    print(f"Content type: {img_response.headers.get('content-type')}")
    img_response.raise_for_status()
    
    # Send to ML detector
    print(f"\nSending to ML detector...")
    files = {"file": ("snapshot.jpg", img_response.content, "image/jpeg")}
    detect_response = requests.post(f"{ML_DETECTOR}/detect", files=files)
    print(f"Detector status: {detect_response.status_code}")
    detect_response.raise_for_status()
    
    result = detect_response.json()
    print(f"\nDetection result:")
    print(f"  deer_detected: {result.get('deer_detected')}")
    print(f"  confidence: {result.get('detection_confidence')}")
    print(f"  detections: {result.get('detections')}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
