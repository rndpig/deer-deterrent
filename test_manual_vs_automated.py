"""
Monitor manual video upload to compare detection results with automated system.
This will help determine if the automated system is actually running detection properly.
"""
import requests
import time
from datetime import datetime
import json

API_URL = "https://deer-api.rndpig.com"

def monitor_manual_upload():
    """Monitor the system during manual video upload to compare results."""
    
    print("="*80)
    print("Manual Upload Detection Comparison Test")
    print("="*80)
    print()
    print("This script will help verify if automated detection is working correctly.")
    print()
    
    # Get baseline - current state before upload
    print("1. Getting baseline state BEFORE manual upload...")
    print()
    
    try:
        response = requests.get(f"{API_URL}/api/videos", timeout=10)
        if response.status_code == 200:
            videos_before = response.json()
            print(f"   Current videos in system: {len(videos_before)}")
            
            if videos_before:
                latest = videos_before[0]
                print(f"   Latest video: {latest.get('filename', 'unknown')}")
                print(f"   Upload date: {latest.get('upload_date', 'unknown')}")
            print()
    except Exception as e:
        print(f"   ⚠ Could not fetch videos: {e}")
        print()
    
    # Get recent detections
    try:
        response = requests.get(f"{API_URL}/api/detections/recent?hours=168", timeout=10)
        if response.status_code == 200:
            detections_before = response.json()
            print(f"   Recent detections (last 7 days): {len(detections_before)}")
            print()
    except Exception as e:
        print(f"   ⚠ Could not fetch detections: {e}")
        print()
    
    # Get Ring events for Jan 16
    try:
        response = requests.get(f"{API_URL}/api/ring-events?hours=168", timeout=10)
        if response.status_code == 200:
            data = response.json()
            events = data.get('events', [])
            
            jan16_events = [
                e for e in events 
                if "2026-01-16 20:00" <= e['timestamp'] <= "2026-01-17 02:00"
            ]
            
            print(f"   Ring events on Jan 16 (8PM-2AM): {len(jan16_events)}")
            
            # Show the specific event at 11:06 PM
            event_at_1106 = [e for e in jan16_events if "23:06" in e['timestamp']]
            if event_at_1106:
                evt = event_at_1106[0]
                print()
                print(f"   Event at ~11:06 PM (Event ID {evt['id']}):")
                print(f"   - Camera: {evt['camera_id']}")
                print(f"   - Timestamp: {evt['timestamp']}")
                print(f"   - Snapshot size: {evt.get('snapshot_size', 0)} bytes")
                print(f"   - Processed: {evt['processed']}")
                print(f"   - Deer detected: {evt.get('deer_detected', False)}")
                if evt.get('detection_confidence'):
                    print(f"   - Confidence: {evt['detection_confidence']:.2%}")
            print()
    except Exception as e:
        print(f"   ⚠ Could not fetch Ring events: {e}")
        print()
    
    print("="*80)
    print("NOW: Upload the Jan 16 video manually through the web interface")
    print("="*80)
    print()
    print("Instructions:")
    print("1. Go to https://deer.rndpig.com")
    print("2. Click 'Upload Video' or similar button")
    print("3. Select the Jan 16, 2026 ~11:06 PM video from your Ring app")
    print("4. Upload and wait for processing to complete")
    print()
    print("Then press Enter to check the results...")
    input()
    
    print()
    print("="*80)
    print("2. Checking results AFTER manual upload...")
    print("="*80)
    print()
    
    # Wait a moment for processing
    print("   Waiting 5 seconds for processing...")
    time.sleep(5)
    print()
    
    # Check for new video
    try:
        response = requests.get(f"{API_URL}/api/videos", timeout=10)
        if response.status_code == 200:
            videos_after = response.json()
            print(f"   Videos in system now: {len(videos_after)}")
            
            # Find the newly uploaded video
            if len(videos_after) > len(videos_before):
                new_video = videos_after[0]  # Should be most recent
                print()
                print(f"   ✓ NEW VIDEO FOUND:")
                print(f"   - Filename: {new_video.get('filename', 'unknown')}")
                print(f"   - Video ID: {new_video.get('id')}")
                print(f"   - Upload date: {new_video.get('upload_date')}")
                print(f"   - Frames: {new_video.get('total_frames', 0)}")
                print(f"   - Duration: {new_video.get('duration_seconds', 0):.1f}s")
                print(f"   - Camera: {new_video.get('camera_name', 'unknown')}")
                
                video_id = new_video.get('id')
                print()
                print("   Checking frames for this video...")
                
                # Get frames for this video
                response2 = requests.get(f"{API_URL}/api/videos/{video_id}/frames", timeout=10)
                if response2.status_code == 200:
                    frames = response2.json()
                    print(f"   - Total frames extracted: {len(frames)}")
                    
                    frames_with_detections = [f for f in frames if f.get('has_detections')]
                    print(f"   - Frames WITH detections: {len(frames_with_detections)}")
                    
                    if frames_with_detections:
                        print()
                        print("   ✓✓✓ DEER DETECTED IN MANUAL UPLOAD! ✓✓✓")
                        print()
                        print(f"   Frames with deer detected: {len(frames_with_detections)}")
                        
                        # Show a few examples
                        for frame in frames_with_detections[:5]:
                            print(f"   - Frame {frame['frame_number']}: {frame.get('detection_count', 0)} detections")
                        
                        print()
                        print("="*80)
                        print("CONCLUSION: Detection algorithm WORKS!")
                        print("="*80)
                        print()
                        print("Since deer WERE detected in manually uploaded video,")
                        print("but NOT detected during automated Ring capture,")
                        print("this confirms the problem is:")
                        print()
                        print("❌ The automated system is NOT properly processing Ring videos")
                        print()
                        print("Possible causes:")
                        print("1. Coordinator using low-res MQTT snapshot instead of video")
                        print("2. Snapshot timing - captured before/after deer in frame")
                        print("3. Video URL not being downloaded and processed")
                        print("4. Only single frame analyzed instead of multiple frames")
                        print()
                        print("Next steps:")
                        print("- Modify coordinator to download and analyze full video")
                        print("- Extract multiple frames from video (not just snapshot)")
                        print("- Or request high-res snapshot with delay")
                        print()
                    else:
                        print()
                        print("   ⚠ NO detections found in manual upload either")
                        print("   This suggests:")
                        print("   - Deer might not be visible in this video")
                        print("   - OR ML model confidence threshold too high")
                        print("   - OR ML model needs retraining")
                        print()
                else:
                    print(f"   ⚠ Could not fetch frames: {response2.status_code}")
            else:
                print("   ⚠ No new video found - upload may have failed")
                print()
    except Exception as e:
        print(f"   ❌ Error checking results: {e}")
        print()
    
    # Check for any new deer detections
    try:
        response = requests.get(f"{API_URL}/api/detections/recent?hours=1", timeout=10)
        if response.status_code == 200:
            detections_after = response.json()
            new_detections = len(detections_after) - len(detections_before)
            
            if new_detections > 0:
                print(f"   ✓ New detections logged: {new_detections}")
                print()
                print("   Recent detection events:")
                for det in detections_after[:3]:
                    ts = det.get('timestamp', 'unknown')
                    cam = det.get('camera_name', det.get('camera_id', 'unknown'))
                    conf = det.get('max_confidence', det.get('confidence', 0))
                    print(f"   - {ts} | {cam} | Confidence: {conf:.2%}")
                print()
    except Exception as e:
        print(f"   ⚠ Could not check detections: {e}")
        print()
    
    print("="*80)
    print("Test complete!")
    print("="*80)


if __name__ == "__main__":
    monitor_manual_upload()
