"""
Check Ring events via the API for January 16, 2026 at 10:06 PM Central time.
"""
import requests
from datetime import datetime, timedelta
import json

API_URL = "https://deer-api.rndpig.com"

def check_ring_events_via_api():
    """Check Ring events via the backend API."""
    
    print("="*80)
    print("Deer Deterrent - Jan 16, 2026 Event Investigation (via API)")
    print("="*80)
    print()
    
    # First, check if coordinator is running and get stats
    print("1. Checking coordinator status...")
    try:
        response = requests.get(f"{API_URL}/api/coordinator/stats", timeout=10)
        if response.status_code == 200:
            stats = response.json()
            print(f"   ✓ Coordinator is running")
            print(f"   Total snapshots: {stats.get('total_snapshots', 0)}")
            print(f"   Last activation: {stats.get('last_activation', 'Never')}")
            print(f"   Active hours: {stats.get('active_hours', False)}")
            print(f"   MQTT connected: {stats.get('mqtt_connected', False)}")
            print()
        else:
            print(f"   ⚠ Coordinator API returned status {response.status_code}")
            print()
    except Exception as e:
        print(f"   ❌ Could not connect to coordinator: {e}")
        print()
    
    # Get Ring events from last 7 days
    print("2. Checking Ring events (last 7 days)...")
    try:
        response = requests.get(f"{API_URL}/api/ring-events?hours=168", timeout=10)
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            total = data.get('total_count', 0)
            
            print(f"   ✓ Found {total} Ring events in last 7 days")
            print()
            
            if total == 0:
                print("   ❌ NO RING EVENTS FOUND!")
                print()
                print("   This indicates:")
                print("   - Ring-MQTT bridge may not be working")
                print("   - MQTT broker may not be running")
                print("   - Coordinator may not be subscribed to Ring topics")
                print("   - Ring cameras may not be triggering motion events")
                print()
                return
            
            # Filter for Jan 16, 2026 around 10:06 PM
            target_start = "2026-01-16 20:00"  # 8 PM local
            target_end = "2026-01-17 02:00"    # 2 AM next day
            
            print(f"3. Filtering for events between {target_start} and {target_end}...")
            jan16_events = [
                e for e in events 
                if target_start <= e['timestamp'] <= target_end
            ]
            
            if jan16_events:
                print(f"   ✓ Found {len(jan16_events)} events in target window:")
                print()
                
                for event in jan16_events:
                    print("   " + "="*76)
                    print(f"   Event ID: {event['id']}")
                    print(f"   Camera ID: {event['camera_id']}")
                    print(f"   Event Type: {event['event_type']}")
                    print(f"   Timestamp: {event['timestamp']}")
                    print(f"   Snapshot Available: {event['snapshot_available']}")
                    if event['snapshot_size']:
                        print(f"   Snapshot Size: {event['snapshot_size']} bytes")
                    if event['recording_url']:
                        print(f"   Recording URL: {event['recording_url'][:80]}...")
                    print(f"   Processed: {event['processed']}")
                    
                    if event['processed']:
                        print(f"   Deer Detected: {event['deer_detected']}")
                        if event['detection_confidence']:
                            print(f"   Confidence: {event['detection_confidence']:.2%}")
                        if event['error_message']:
                            print(f"   ERROR: {event['error_message']}")
                    else:
                        print("   ⚠ EVENT WAS NOT PROCESSED BY ML DETECTOR")
                    print()
            else:
                print(f"   ❌ No events found in target window (10:06 PM on Jan 16)")
                print()
                print("   Showing most recent events instead:")
                print()
                
                for event in events[:5]:
                    print(f"   - {event['timestamp']} | Camera: {event['camera_id']} | Type: {event['event_type']} | Processed: {event['processed']}")
                print()
        else:
            print(f"   ⚠ API returned status {response.status_code}")
            print()
    except Exception as e:
        print(f"   ❌ Could not fetch Ring events: {e}")
        print()
    
    # Get coordinator logs
    print("4. Checking coordinator logs (last 100 lines)...")
    try:
        response = requests.get(f"{API_URL}/api/coordinator/logs?lines=100", timeout=10)
        if response.status_code == 200:
            data = response.json()
            logs = data.get('logs', '')
            
            # Filter for Jan 16-17
            jan16_log_lines = []
            for line in logs.split('\n'):
                if '2026-01-16' in line or '2026-01-17' in line:
                    jan16_log_lines.append(line)
            
            if jan16_log_lines:
                print(f"   ✓ Found {len(jan16_log_lines)} log entries from Jan 16-17:")
                print()
                for line in jan16_log_lines:
                    print(f"   {line}")
                print()
            else:
                print("   ⚠ No log entries from Jan 16-17 found")
                print()
                print("   Showing last 10 lines of coordinator logs:")
                print()
                for line in logs.split('\n')[-10:]:
                    if line.strip():
                        print(f"   {line}")
                print()
        else:
            print(f"   ⚠ Could not fetch logs: status {response.status_code}")
            print()
    except Exception as e:
        print(f"   ⚠ Could not fetch coordinator logs: {e}")
        print()
    
    # Get recent detections to see if system is working
    print("5. Checking recent detections (last 7 days)...")
    try:
        response = requests.get(f"{API_URL}/api/detections/recent?hours=168", timeout=10)
        if response.status_code == 200:
            detections = response.json()
            print(f"   ✓ Found {len(detections)} deer detections in last 7 days")
            
            if detections:
                print()
                print("   Most recent detections:")
                for det in detections[:5]:
                    ts = det.get('timestamp', 'unknown')
                    cam = det.get('camera_name', det.get('camera_id', 'unknown'))
                    conf = det.get('max_confidence', det.get('confidence', 0))
                    print(f"   - {ts} | {cam} | Confidence: {conf:.2%}")
            else:
                print("   ⚠ No deer detections in last 7 days")
            print()
        else:
            print(f"   ⚠ Could not fetch detections: status {response.status_code}")
            print()
    except Exception as e:
        print(f"   ⚠ Could not fetch detections: {e}")
        print()
    
    print("="*80)
    print("Investigation complete")
    print("="*80)


if __name__ == "__main__":
    check_ring_events_via_api()
