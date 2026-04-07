#!/usr/bin/env python3
"""
Capture reference images from all Ring cameras at regular intervals.
Designed to run during daylight hours to get good lighting for heatmap backgrounds.

Usage:
    python3 capture_reference_images.py

The script will capture images every 15 minutes between the configured start/end times.
Images are saved to: /app/data/reference_images/{camera_name}/{timestamp}.jpg
"""

import os
import sys
import time
import json
import signal
from datetime import datetime, timedelta
from pathlib import Path

import paho.mqtt.client as mqtt

# Configuration
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/app/data/reference_images"))
CAPTURE_INTERVAL_MINUTES = int(os.getenv("CAPTURE_INTERVAL", 15))
TIMEZONE = os.getenv("TZ", "America/Chicago")

# Time window for capture (24-hour format, local time)
# Default: noon to 4pm
START_HOUR = int(os.getenv("START_HOUR", 12))
END_HOUR = int(os.getenv("END_HOUR", 16))

# Camera mapping
CAMERAS = {
    "c4dbad08f862": "Side",
    "587a624d3fae": "Driveway", 
    "4439c4de7a79": "FrontDoor",
    "f045dae9383a": "Back",
    "10cea9e4511f": "Woods",
}

# MQTT topic pattern for snapshots
SNAPSHOT_TOPIC = "ring/+/camera/+/snapshot/image"

# State
last_capture_time = {}
captured_count = {cam_id: 0 for cam_id in CAMERAS}
running = True


def signal_handler(sig, frame):
    global running
    print("\nShutting down...")
    running = False


def is_in_capture_window():
    """Check if current time is within the capture window."""
    now = datetime.now()
    return START_HOUR <= now.hour < END_HOUR


def should_capture(camera_id):
    """Check if we should capture this camera (based on interval)."""
    now = datetime.now()
    if camera_id not in last_capture_time:
        return True
    
    elapsed = (now - last_capture_time[camera_id]).total_seconds()
    return elapsed >= CAPTURE_INTERVAL_MINUTES * 60


def save_image(camera_id, image_data):
    """Save image to disk."""
    camera_name = CAMERAS.get(camera_id, camera_id)
    camera_dir = OUTPUT_DIR / camera_name
    camera_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}.jpg"
    filepath = camera_dir / filename
    
    with open(filepath, "wb") as f:
        f.write(image_data)
    
    last_capture_time[camera_id] = datetime.now()
    captured_count[camera_id] += 1
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Saved: {camera_name}/{filename} "
          f"({len(image_data):,} bytes) - Total: {captured_count[camera_id]}")


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
        client.subscribe(SNAPSHOT_TOPIC)
        print(f"Subscribed to: {SNAPSHOT_TOPIC}")
    else:
        print(f"Failed to connect, return code: {rc}")


def on_message(client, userdata, msg):
    """Handle incoming snapshot messages."""
    if not is_in_capture_window():
        return
    
    # Extract camera ID from topic: ring/xxx/camera/{camera_id}/snapshot/image
    parts = msg.topic.split("/")
    if len(parts) >= 4:
        camera_id = parts[3]
        
        if camera_id in CAMERAS and should_capture(camera_id):
            save_image(camera_id, msg.payload)


def print_status():
    """Print current status."""
    now = datetime.now()
    in_window = is_in_capture_window()
    
    print(f"\n{'='*60}")
    print(f"Reference Image Capture - {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    print(f"Capture window: {START_HOUR:02d}:00 - {END_HOUR:02d}:00")
    print(f"Currently: {'IN WINDOW - capturing' if in_window else 'OUTSIDE WINDOW - waiting'}")
    print(f"Interval: Every {CAPTURE_INTERVAL_MINUTES} minutes")
    print(f"Output: {OUTPUT_DIR}")
    print(f"\nCameras:")
    for cam_id, name in CAMERAS.items():
        count = captured_count[cam_id]
        last = last_capture_time.get(cam_id)
        last_str = last.strftime("%H:%M:%S") if last else "never"
        print(f"  {name:12} - Captured: {count:3}, Last: {last_str}")
    print(f"{'='*60}\n")


def main():
    global running
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print_status()
    
    # Setup MQTT client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}")
        sys.exit(1)
    
    client.loop_start()
    
    # Main loop - print status every minute
    last_status = datetime.now()
    while running:
        time.sleep(1)
        
        # Print status every 5 minutes
        if (datetime.now() - last_status).total_seconds() >= 300:
            print_status()
            last_status = datetime.now()
    
    client.loop_stop()
    client.disconnect()
    
    print("\n" + "="*60)
    print("Final Summary:")
    for cam_id, name in CAMERAS.items():
        print(f"  {name}: {captured_count[cam_id]} images captured")
    print("="*60)


if __name__ == "__main__":
    main()
