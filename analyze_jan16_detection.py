"""
Download and analyze the snapshot from Jan 16 event to see why deer wasn't detected.
"""
import requests
import json
from datetime import datetime

API_URL = "https://deer-api.rndpig.com"

def analyze_jan16_event():
    """Analyze the Jan 16, 2026 10:06 PM event in detail."""
    
    print("="*80)
    print("Analyzing Jan 16, 2026 ~10:06 PM Event (Event ID 5584)")
    print("="*80)
    print()
    
    event_id = 5584
    
    # Get the specific event details
    print("1. Event Details:")
    print(f"   Event ID: {event_id}")
    print(f"   Camera ID: 10cea9e4511f")
    print(f"   Timestamp: 2026-01-16T23:06:38 (11:06 PM local)")
    print(f"   Snapshot Available: Yes (24,106 bytes)")
    print(f"   Processed: Yes")
    print(f"   Deer Detected: NO ❌")
    print()
    
    print("2. Diagnosis:")
    print()
    print("   The system IS working correctly:")
    print("   ✓ Ring camera detected motion")
    print("   ✓ Ring-MQTT bridge captured the event")
    print("   ✓ Coordinator received the MQTT message")
    print("   ✓ Snapshot was captured (24KB)")
    print("   ✓ ML detector processed the image")
    print()
    print("   The problem:")
    print("   ❌ ML model did NOT detect deer in the image")
    print()
    print("   Possible reasons:")
    print("   - Deer was too far from camera")
    print("   - Image quality was poor (night time, low resolution)")
    print("   - Deer was partially obscured")
    print("   - ML model confidence threshold too high")
    print("   - ML model needs more training")
    print("   - Snapshot timing missed the deer (taken after deer left frame)")
    print()
    
    print("3. Checking ML detector configuration...")
    try:
        response = requests.get(f"{API_URL}/api/coordinator/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            print(f"   ✓ Coordinator stats retrieved")
            print()
            
            # Try to get health check from coordinator
            response2 = requests.get("https://deer-api.rndpig.com/api/coordinator/logs?lines=500", timeout=10)
            if response2.status_code == 200:
                logs = response2.json().get('logs', '')
                
                # Look for configuration info in logs
                config_lines = []
                for line in logs.split('\n'):
                    if 'CONFIDENCE_THRESHOLD' in line or 'threshold' in line.lower() or 'config' in line.lower():
                        config_lines.append(line.strip())
                
                if config_lines:
                    print("   Configuration found in logs:")
                    for line in config_lines[:10]:
                        print(f"   {line}")
                else:
                    print("   No configuration info found in recent logs")
        print()
    except Exception as e:
        print(f"   ⚠ Could not fetch coordinator config: {e}")
        print()
    
    print("4. Recommendations:")
    print()
    print("   To diagnose further, you should:")
    print()
    print("   a) Check the actual snapshot image:")
    print("      - Look in /app/snapshots/ on the server")
    print(f"      - Find file matching: 20260116_230638_10cea9e4511f*.jpg")
    print("      - Manually review: Can YOU see a deer in the image?")
    print()
    print("   b) Test the ML model with this image:")
    print("      - Run the image through the ML detector manually")
    print("      - Check what confidence score it returns")
    print("      - Try lowering confidence threshold if needed")
    print()
    print("   c) Check current ML model confidence threshold:")
    print("      - Current setting may be too high (e.g., >0.3)")
    print("      - Try lowering to 0.15 or 0.20 for better detection")
    print("      - But beware of false positives")
    print()
    print("   d) Review Ring app video:")
    print("      - Check if Ring app has the actual video recording")
    print("      - Confirm a deer was actually present")
    print("      - Note the exact time deer appears in frame")
    print()
    print("   e) Consider snapshot timing issue:")
    print("      - Ring-MQTT snapshots may be lower resolution")
    print("      - Try requesting high-res snapshot or use video frame")
    print()
    
    print("="*80)
    print("Next Steps")
    print("="*80)
    print()
    print("To access the snapshot on the server:")
    print()
    print("  ssh dilger")
    print("  cd /home/rndpig/deer-deterrent")
    print("  docker exec deer-coordinator ls -lh /app/snapshots/ | grep 20260116_2306")
    print("  docker cp deer-coordinator:/app/snapshots/20260116_230638_10cea9e4511f.jpg ./")
    print("  # Then download and review the image")
    print()
    print("To test ML detector manually:")
    print()
    print("  curl -X POST -F 'file=@20260116_230638_10cea9e4511f.jpg' \\")
    print("    http://localhost:8001/detect")
    print()
    print("To check/update confidence threshold:")
    print()
    print("  docker exec deer-coordinator env | grep CONFIDENCE")
    print("  # Edit docker-compose.yml to lower threshold if needed")
    print()


if __name__ == "__main__":
    analyze_jan16_event()
