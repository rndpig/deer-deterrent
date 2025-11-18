"""
Rain Bird ESP-Me Cloud API integration.
The ESP-Me series uses Rain Bird's cloud API rather than local network control.
"""
import os
import requests
from typing import List, Optional, Dict
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()


class RainbirdCloudController:
    """Client for controlling Rain Bird ESP-Me via cloud API."""
    
    # Rain Bird Cloud API endpoints
    BASE_URL = "https://api.rainbird.com/v1"
    
    def __init__(self):
        """Initialize Rain Bird cloud controller client."""
        self.email = os.getenv("RAINBIRD_EMAIL")
        self.password = os.getenv("RAINBIRD_PASSWORD")
        
        if not self.email or not self.password:
            raise ValueError(
                "Rain Bird credentials not found. "
                "Please set RAINBIRD_EMAIL and RAINBIRD_PASSWORD in .env file"
            )
        
        self.session = requests.Session()
        self.token = None
        self.device_id = None
        
        # Zone tracking for cooldown management
        self.zone_last_activated = {}
        
        print("Initializing Rain Bird cloud connection...")
        self._authenticate()
    
    def _authenticate(self) -> bool:
        """Authenticate with Rain Bird cloud API."""
        try:
            # Note: The actual Rain Bird API authentication may differ
            # This is a template based on common OAuth2 patterns
            
            # Option 1: Try standard OAuth2 token endpoint
            response = self.session.post(
                f"{self.BASE_URL}/auth/token",
                json={
                    "email": self.email,
                    "password": self.password,
                    "grant_type": "password"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.session.headers.update({
                    "Authorization": f"Bearer {self.token}"
                })
                print("✓ Authenticated with Rain Bird cloud")
                return True
            else:
                print(f"⚠ Authentication response: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"✗ Authentication error: {e}")
            return False
    
    def get_devices(self) -> List[Dict]:
        """
        Get list of Rain Bird devices associated with account.
        
        Returns:
            List of device information dictionaries
        """
        try:
            response = self.session.get(
                f"{self.BASE_URL}/devices",
                timeout=10
            )
            
            if response.status_code == 200:
                devices = response.json()
                
                if devices:
                    # Store first device as default
                    self.device_id = devices[0].get("id")
                    print(f"✓ Found {len(devices)} device(s)")
                    for dev in devices:
                        print(f"  - {dev.get('name', 'Unknown')} (ID: {dev.get('id')})")
                
                return devices
            else:
                print(f"⚠ Failed to get devices: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"✗ Error getting devices: {e}")
            return []
    
    def get_zones(self, device_id: Optional[str] = None) -> List[Dict]:
        """
        Get list of zones for a device.
        
        Args:
            device_id: Device ID (uses default if not provided)
            
        Returns:
            List of zone information
        """
        device_id = device_id or self.device_id
        
        if not device_id:
            print("⚠ No device ID available")
            return []
        
        try:
            response = self.session.get(
                f"{self.BASE_URL}/devices/{device_id}/zones",
                timeout=10
            )
            
            if response.status_code == 200:
                zones = response.json()
                print(f"✓ Found {len(zones)} zone(s)")
                for zone in zones:
                    print(f"  - Zone {zone.get('number')}: {zone.get('name')}")
                return zones
            else:
                print(f"⚠ Failed to get zones: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"✗ Error getting zones: {e}")
            return []
    
    def activate_zone(
        self,
        zone: int,
        duration: int = 30,
        cooldown: int = 300,
        device_id: Optional[str] = None
    ) -> bool:
        """
        Activate a specific irrigation zone.
        
        Args:
            zone: Zone number to activate
            duration: How long to run in seconds (converted to minutes for API)
            cooldown: Minimum seconds since last activation
            device_id: Device ID (uses default if not provided)
            
        Returns:
            True if activation successful
        """
        device_id = device_id or self.device_id
        
        if not device_id:
            print("⚠ No device ID available")
            return False
        
        # Check cooldown
        if not self._check_cooldown(zone, cooldown):
            return False
        
        # Convert seconds to minutes (Rain Bird API typically uses minutes)
        duration_minutes = max(1, duration // 60)
        
        print(f"Activating Rain Bird zone {zone} for {duration_minutes} minute(s)...")
        
        try:
            response = self.session.post(
                f"{self.BASE_URL}/devices/{device_id}/zones/{zone}/start",
                json={
                    "duration": duration_minutes
                },
                timeout=10
            )
            
            if response.status_code in [200, 201, 204]:
                self.zone_last_activated[zone] = datetime.now()
                print(f"✓ Zone {zone} activated successfully")
                return True
            else:
                print(f"✗ Failed to activate zone {zone}: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"✗ Error activating zone {zone}: {e}")
            return False
    
    def stop_zone(self, zone: int, device_id: Optional[str] = None) -> bool:
        """
        Stop a running zone.
        
        Args:
            zone: Zone number to stop
            device_id: Device ID (uses default if not provided)
            
        Returns:
            True if successful
        """
        device_id = device_id or self.device_id
        
        if not device_id:
            print("⚠ No device ID available")
            return False
        
        print(f"Stopping Rain Bird zone {zone}...")
        
        try:
            response = self.session.post(
                f"{self.BASE_URL}/devices/{device_id}/zones/{zone}/stop",
                timeout=10
            )
            
            if response.status_code in [200, 201, 204]:
                print(f"✓ Zone {zone} stopped")
                return True
            else:
                print(f"✗ Failed to stop zone {zone}: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✗ Error stopping zone {zone}: {e}")
            return False
    
    def _check_cooldown(self, zone: int, cooldown: int) -> bool:
        """Check if enough time has passed since last activation."""
        if zone not in self.zone_last_activated:
            return True
        
        last_activated = self.zone_last_activated[zone]
        elapsed = (datetime.now() - last_activated).total_seconds()
        
        if elapsed < cooldown:
            remaining = int(cooldown - elapsed)
            print(
                f"⏳ Zone {zone} on cooldown. "
                f"{remaining}s remaining until next activation."
            )
            return False
        
        return True


def main():
    """Test Rain Bird cloud controller integration."""
    print("Rain Bird ESP-Me Cloud Integration Test")
    print("=" * 50)
    
    try:
        controller = RainbirdCloudController()
        
        # Get devices
        print("\nGetting devices...")
        devices = controller.get_devices()
        
        if not devices:
            print("\n⚠ No devices found or API connection issue")
            print("\nNOTE: The Rain Bird cloud API endpoints may differ from this")
            print("implementation. You may need to:")
            print("1. Check Rain Bird's official API documentation")
            print("2. Use browser dev tools to inspect the Rain Bird mobile app")
            print("3. Or use a third-party library like 'pyrainbird'")
            return
        
        # Get zones
        print("\nGetting zones...")
        zones = controller.get_zones()
        
        print("\n⚠ Actual zone activation disabled in test mode")
        print("To test activation, uncomment the code below!")
        
        # Uncomment to test (USE WITH CAUTION - will actually run irrigation!)
        # print("\nTesting zone 2 (Garage North) for 1 minute...")
        # controller.activate_zone(2, duration=60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

