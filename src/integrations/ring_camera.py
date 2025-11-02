"""
Ring camera integration module for accessing camera feeds.
"""
import os
from typing import List, Optional
from ring_doorbell import Ring, Auth
from pathlib import Path
from dotenv import load_dotenv
import cv2
import numpy as np

load_dotenv()


class RingCameraClient:
    """Client for accessing Ring camera feeds."""
    
    def __init__(self):
        """Initialize Ring API client."""
        self.username = os.getenv("RING_USERNAME")
        self.password = os.getenv("RING_PASSWORD")
        
        if not self.username or not self.password:
            raise ValueError(
                "Ring credentials not found. "
                "Please set RING_USERNAME and RING_PASSWORD in .env file"
            )
        
        self.ring = None
        self.devices = None
        self._authenticate()
    
    def _authenticate(self) -> None:
        """Authenticate with Ring API."""
        print("Authenticating with Ring API...")
        
        try:
            # Updated for newer ring-doorbell API
            cache_file = Path("ring_token.cache")
            
            auth = Auth("DeerDeterrent/1.0", None, cache_file)
            
            # Try to load existing token first
            if cache_file.exists():
                print("Using cached authentication token...")
                auth.fetch_token()
            else:
                print("Fetching new authentication token...")
                auth.fetch_token(self.username, self.password)
            
            self.ring = Ring(auth)
            self.ring.update_data()
            self.devices = self.ring.devices()
            
            print(f"✓ Successfully authenticated")
            self._list_devices()
            
        except Exception as e:
            print(f"✗ Authentication failed: {e}")
            import traceback
            traceback.print_exc()
            print("\nTroubleshooting:")
            print("  - Verify RING_USERNAME and RING_PASSWORD in .env")
            print("  - If 2FA is enabled, you need to get a 2FA code")
            print("  - Try deleting ring_token.cache if it exists")
            raise
    
    def _list_devices(self) -> None:
        """List all available Ring devices."""
        print("\nAvailable Ring devices:")
        
        if self.devices.get('doorbots'):
            print("\n  Doorbells:")
            for device in self.devices['doorbots']:
                print(f"    - {device.name} (ID: {device.id})")
        
        if self.devices.get('stickup_cams'):
            print("\n  Cameras:")
            for device in self.devices['stickup_cams']:
                print(f"    - {device.name} (ID: {device.id})")
    
    def get_camera_by_name(self, name: str):
        """Get a camera device by name."""
        # Check doorbells
        for device in self.devices.get('doorbots', []):
            if device.name.lower() == name.lower():
                return device
        
        # Check cameras
        for device in self.devices.get('stickup_cams', []):
            if device.name.lower() == name.lower():
                return device
        
        return None
    
    def get_latest_snapshot(self, camera_name: str) -> Optional[np.ndarray]:
        """
        Get the latest snapshot from a camera.
        
        Args:
            camera_name: Name of the camera
            
        Returns:
            Image as numpy array (BGR format) or None if failed
        """
        device = self.get_camera_by_name(camera_name)
        
        if not device:
            print(f"Camera '{camera_name}' not found")
            return None
        
        try:
            # Request a new snapshot (this may take a few seconds)
            device.update_health_data()
            
            # Get the snapshot URL
            snapshot_url = device.get_snapshot(timeout=10)
            
            if snapshot_url:
                # Download and convert to numpy array
                import requests
                response = requests.get(snapshot_url)
                
                if response.status_code == 200:
                    # Convert to numpy array
                    image_array = np.frombuffer(response.content, np.uint8)
                    image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                    return image
            
            return None
            
        except Exception as e:
            print(f"Error getting snapshot from {camera_name}: {e}")
            return None
    
    def get_latest_recording(self, camera_name: str) -> Optional[str]:
        """
        Get URL of the latest recording from a camera.
        
        Args:
            camera_name: Name of the camera
            
        Returns:
            URL to the latest recording or None
        """
        device = self.get_camera_by_name(camera_name)
        
        if not device:
            print(f"Camera '{camera_name}' not found")
            return None
        
        try:
            # Get history
            history = device.history(limit=1)
            
            if history:
                latest = history[0]
                return latest['recording']['url']
            
            return None
            
        except Exception as e:
            print(f"Error getting recording from {camera_name}: {e}")
            return None
    
    def get_all_cameras(self) -> List[dict]:
        """
        Get list of all cameras with their details.
        
        Returns:
            List of camera info dictionaries
        """
        cameras = []
        
        for device in self.devices.get('doorbots', []):
            cameras.append({
                'name': device.name,
                'id': device.id,
                'type': 'doorbell',
                'battery_life': device.battery_life
            })
        
        for device in self.devices.get('stickup_cams', []):
            cameras.append({
                'name': device.name,
                'id': device.id,
                'type': 'camera',
                'battery_life': device.battery_life
            })
        
        return cameras


def main():
    """Test Ring camera integration."""
    print("Ring Camera Integration Test")
    print("=" * 50)
    
    try:
        client = RingCameraClient()
        
        cameras = client.get_all_cameras()
        print(f"\nFound {len(cameras)} camera(s)")
        
        # Test getting a snapshot from the first camera
        if cameras:
            test_camera = cameras[0]['name']
            print(f"\nTesting snapshot from: {test_camera}")
            
            image = client.get_latest_snapshot(test_camera)
            
            if image is not None:
                print(f"✓ Successfully captured snapshot: {image.shape}")
                
                # Save test image
                output_dir = Path("temp")
                output_dir.mkdir(exist_ok=True)
                output_path = output_dir / f"ring_test_snapshot.jpg"
                cv2.imwrite(str(output_path), image)
                print(f"✓ Saved test image to: {output_path}")
            else:
                print("✗ Failed to capture snapshot")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")


if __name__ == "__main__":
    main()
