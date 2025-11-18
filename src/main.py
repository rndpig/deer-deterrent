"""
Main application for real-time deer detection and deterrent system.
"""
import os
import time
import yaml
from pathlib import Path
from datetime import datetime, time as dt_time
from typing import Dict, List
from collections import defaultdict

from src.integrations.ring_camera import RingCameraClient
from src.integrations.rainbird_controller import RainbirdController
from src.inference.detector import DeerDetector
from dotenv import load_dotenv

load_dotenv()


class DeerDeterrentSystem:
    """Main system orchestrating detection and deterrent actions."""
    
    def __init__(self, config_path: str = "configs/zones.yaml"):
        """Initialize the deer deterrent system."""
        print("=" * 60)
        print("Deer Deterrent System - Initializing")
        print("=" * 60)
        
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.zones = self.config['zones']
        self.cameras = self.config['cameras']
        self.settings = self.config['settings']
        
        # Load seasonal settings
        self.season_start = os.getenv("SEASON_START_DATE", "04-01")
        self.season_end = os.getenv("SEASON_END_DATE", "10-31")
        
        # Initialize components
        print("\n[1/3] Initializing deer detector...")
        model_path = os.getenv("MODEL_PATH", "models/production/best.pt")
        conf_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", self.settings['min_confidence']))
        self.detector = DeerDetector(model_path=model_path, conf_threshold=conf_threshold)
        
        print("\n[2/3] Connecting to Ring cameras...")
        self.ring_client = RingCameraClient()
        
        print("\n[3/3] Connecting to Rainbird controller...")
        self.rainbird = RainbirdController()
        
        # Tracking for confirmation detections
        self.recent_detections = defaultdict(list)
        
        # Dry run mode
        self.dry_run = self.settings.get('dry_run', False)
        if self.dry_run:
            print("\n⚠ DRY RUN MODE - Irrigation will NOT be activated")
        
        print("\n✓ System initialized successfully")
        self._print_season_status()
        print("=" * 60)
    
    def _print_season_status(self) -> None:
        """Print current seasonal operation status."""
        if self.is_in_season():
            print(f"✓ ACTIVE SEASON ({self.season_start} to {self.season_end})")
        else:
            print(f"⚠ OFF-SEASON (Active: {self.season_start} to {self.season_end})")
            print("  Irrigation system winterized - detection only mode")
    
    def is_in_season(self) -> bool:
        """Check if current date is within irrigation season."""
        now = datetime.now()
        current_year = now.year
        
        # Parse season dates
        start_month, start_day = map(int, self.season_start.split('-'))
        end_month, end_day = map(int, self.season_end.split('-'))
        
        # Create datetime objects for this year
        season_start = datetime(current_year, start_month, start_day)
        season_end = datetime(current_year, end_month, end_day)
        
        # Handle season spanning year boundary (e.g., Nov-Mar)
        if season_start > season_end:
            # Season crosses year boundary
            return now >= season_start or now <= season_end
        else:
            # Normal season within same year
            return season_start <= now <= season_end
    
    def is_active_hours(self) -> bool:
        """Check if current time is within active hours."""
        if not self.settings['active_hours']['enabled']:
            return True
        
        now = datetime.now().time()
        start_hour = self.settings['active_hours']['start']
        end_hour = self.settings['active_hours']['end']
        
        start_time = dt_time(start_hour, 0)
        end_time = dt_time(end_hour, 0)
        
        # Handle overnight period (e.g., 20:00 to 6:00)
        if start_time > end_time:
            return now >= start_time or now <= end_time
        else:
            return start_time <= now <= end_time
    
    def process_camera(self, camera_config: dict) -> None:
        """Process a single camera feed."""
        camera_id = camera_config['id']
        camera_name = camera_config['name']
        
        if not camera_config['enabled']:
            return
        
        # Get latest snapshot
        image = self.ring_client.get_latest_snapshot(camera_name)
        
        if image is None:
            print(f"⚠ Failed to get snapshot from {camera_name}")
            return
        
        # Get zones for this camera
        camera_zones = [z for z in self.zones if z['camera_id'] == camera_id]
        
        if not camera_zones:
            return
        
        # Detect deer in zones
        zone_detections = self.detector.detect_in_zones(image, camera_zones)
        
        # Process detections
        for zone_name, detections in zone_detections.items():
            self.handle_zone_detection(zone_name, detections, camera_name)
    
    def handle_zone_detection(
        self,
        zone_name: str,
        detections: List[dict],
        camera_name: str
    ) -> None:
        """Handle deer detection in a specific zone."""
        if not detections:
            return
        
        # Get zone configuration
        zone = next(z for z in self.zones if z['name'] == zone_name)
        
        # Check if confirmation is required
        if self.settings['detection_confirmation']['enabled']:
            if not self._confirm_detection(zone_name, detections):
                return
        
        # Log detection
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        deer_count = len(detections)
        max_conf = max(d['confidence'] for d in detections)
        
        print(f"\n🦌 [{timestamp}] DEER DETECTED!")
        print(f"   Camera: {camera_name}")
        print(f"   Zone: {zone_name}")
        print(f"   Count: {deer_count}")
        print(f"   Confidence: {max_conf:.2f}")
        
        # Activate irrigation
        self.activate_deterrent(zone)
    
    def _confirm_detection(self, zone_name: str, detections: List[dict]) -> bool:
        """
        Require multiple detections within a time window before triggering.
        
        Returns:
            True if detection is confirmed
        """
        required = self.settings['detection_confirmation']['required_detections']
        window = self.settings['detection_confirmation']['within_seconds']
        
        now = time.time()
        
        # Add current detection
        self.recent_detections[zone_name].append({
            'time': now,
            'count': len(detections)
        })
        
        # Remove old detections outside the window
        self.recent_detections[zone_name] = [
            d for d in self.recent_detections[zone_name]
            if now - d['time'] <= window
        ]
        
        # Check if we have enough confirmations
        return len(self.recent_detections[zone_name]) >= required
    
    def activate_deterrent(self, zone: dict) -> None:
        """Activate irrigation for a zone."""
        zone_name = zone['name']
        irrigation_zones = zone['irrigation_zones']
        duration = self.settings['irrigation_duration']
        cooldown = self.settings['zone_cooldown']
        
        # Check if in season
        if not self.is_in_season():
            print(f"   ⚠ OFF-SEASON: Irrigation not activated (system winterized)")
            print(f"   ℹ Detection logged for analysis")
            return
        
        if self.dry_run:
            print(f"   [DRY RUN] Would activate irrigation: zones {irrigation_zones}")
            print(f"   [DRY RUN] Duration: {duration}s")
        else:
            print(f"   💦 Activating irrigation: zones {irrigation_zones}")
            success = self.rainbird.activate_multiple_zones(
                irrigation_zones,
                duration=duration,
                cooldown=cooldown
            )
            
            if success:
                print(f"   ✓ Deterrent activated for {duration}s")
            else:
                print(f"   ✗ Failed to activate deterrent")
    
    def run(self) -> None:
        """Main run loop for continuous monitoring."""
        print("\n" + "=" * 60)
        print("Starting continuous monitoring...")
        print("Press Ctrl+C to stop")
        print("=" * 60 + "\n")
        
        try:
            while True:
                # Check if we're in active hours
                if not self.is_active_hours():
                    current_time = datetime.now().strftime("%H:%M:%S")
                    print(f"[{current_time}] Outside active hours, waiting...")
                    time.sleep(60)  # Check every minute
                    continue
                
                # Process each enabled camera
                for camera in self.cameras:
                    if camera['enabled']:
                        try:
                            self.process_camera(camera)
                        except Exception as e:
                            print(f"Error processing {camera['name']}: {e}")
                        
                        # Wait between cameras
                        time.sleep(camera.get('check_interval', 2))
                
                # Small delay between full cycles
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n" + "=" * 60)
            print("Shutting down deer deterrent system...")
            print("=" * 60)
            print("✓ System stopped")


def main():
    """Main entry point."""
    try:
        system = DeerDeterrentSystem()
        system.run()
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
