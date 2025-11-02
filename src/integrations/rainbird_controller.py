"""
Rainbird irrigation controller integration module.
"""
import os
import requests
from typing import List, Optional
from dotenv import load_dotenv
import time
from datetime import datetime

load_dotenv()


class RainbirdController:
    """Client for controlling Rainbird irrigation system."""
    
    def __init__(self):
        """Initialize Rainbird controller client."""
        self.host = os.getenv("RAINBIRD_HOST")
        self.password = os.getenv("RAINBIRD_PASSWORD")
        
        if not self.host or not self.password:
            raise ValueError(
                "Rainbird credentials not found. "
                "Please set RAINBIRD_HOST and RAINBIRD_PASSWORD in .env file"
            )
        
        self.base_url = f"http://{self.host}"
        self.session = requests.Session()
        
        # Zone tracking for cooldown management
        self.zone_last_activated = {}
    
    def test_connection(self) -> bool:
        """Test connection to Rainbird controller."""
        try:
            response = self.session.get(
                f"{self.base_url}/stick",
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
    
    def activate_zone(
        self,
        zone: int,
        duration: int = 30,
        cooldown: int = 300
    ) -> bool:
        """
        Activate a specific irrigation zone.
        
        Args:
            zone: Zone number to activate (1-based)
            duration: How long to run in seconds
            cooldown: Minimum seconds since last activation (default 5 min)
            
        Returns:
            True if activation successful, False otherwise
        """
        # Check cooldown
        if not self._check_cooldown(zone, cooldown):
            return False
        
        print(f"Activating Rainbird zone {zone} for {duration} seconds...")
        
        try:
            # Rainbird API typically uses a simple HTTP request
            # The exact endpoint may vary by model - adjust as needed
            response = self.session.post(
                f"{self.base_url}/stick",
                json={
                    "id": zone,
                    "duration": duration
                },
                auth=("admin", self.password),
                timeout=10
            )
            
            if response.status_code in [200, 201, 204]:
                self.zone_last_activated[zone] = datetime.now()
                print(f"✓ Zone {zone} activated successfully")
                return True
            else:
                print(f"✗ Failed to activate zone {zone}: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✗ Error activating zone {zone}: {e}")
            return False
    
    def activate_multiple_zones(
        self,
        zones: List[int],
        duration: int = 30,
        cooldown: int = 300
    ) -> bool:
        """
        Activate multiple zones simultaneously or in sequence.
        
        Args:
            zones: List of zone numbers to activate
            duration: How long to run each zone in seconds
            cooldown: Minimum seconds since last activation
            
        Returns:
            True if all activations successful
        """
        print(f"Activating zones {zones} for {duration} seconds each...")
        
        success = True
        for zone in zones:
            if not self.activate_zone(zone, duration, cooldown):
                success = False
        
        return success
    
    def stop_zone(self, zone: int) -> bool:
        """
        Stop a running zone.
        
        Args:
            zone: Zone number to stop
            
        Returns:
            True if successful
        """
        print(f"Stopping Rainbird zone {zone}...")
        
        try:
            response = self.session.post(
                f"{self.base_url}/stick",
                json={
                    "id": zone,
                    "duration": 0  # 0 duration stops the zone
                },
                auth=("admin", self.password),
                timeout=10
            )
            
            if response.status_code in [200, 201, 204]:
                print(f"✓ Zone {zone} stopped")
                return True
            else:
                print(f"✗ Failed to stop zone {zone}")
                return False
                
        except Exception as e:
            print(f"✗ Error stopping zone {zone}: {e}")
            return False
    
    def stop_all_zones(self) -> bool:
        """Stop all running zones."""
        print("Stopping all zones...")
        
        try:
            response = self.session.post(
                f"{self.base_url}/stick",
                json={"stopAll": True},
                auth=("admin", self.password),
                timeout=10
            )
            
            if response.status_code in [200, 201, 204]:
                print("✓ All zones stopped")
                return True
            else:
                print("✗ Failed to stop all zones")
                return False
                
        except Exception as e:
            print(f"✗ Error stopping all zones: {e}")
            return False
    
    def _check_cooldown(self, zone: int, cooldown: int) -> bool:
        """
        Check if enough time has passed since last activation.
        
        Args:
            zone: Zone number to check
            cooldown: Required cooldown period in seconds
            
        Returns:
            True if zone can be activated
        """
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
    
    def get_zone_status(self) -> dict:
        """
        Get status of all zones.
        
        Returns:
            Dictionary with zone status information
        """
        try:
            response = self.session.get(
                f"{self.base_url}/stick",
                auth=("admin", self.password),
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            
        except Exception as e:
            print(f"Error getting zone status: {e}")
        
        return {}


def main():
    """Test Rainbird controller integration."""
    print("Rainbird Controller Integration Test")
    print("=" * 50)
    
    try:
        controller = RainbirdController()
        
        # Test connection
        print("\nTesting connection...")
        if controller.test_connection():
            print("✓ Connected to Rainbird controller")
        else:
            print("✗ Connection failed")
            print("\nNote: The Rainbird API implementation may vary by model.")
            print("You may need to adjust the endpoints in ring_camera.py")
            print("based on your specific controller's documentation.")
            return
        
        # Get status
        print("\nGetting zone status...")
        status = controller.get_zone_status()
        print(f"Status: {status}")
        
        print("\n⚠ Actual zone activation disabled in test mode")
        print("To test activation, uncomment the code below and run carefully!")
        
        # Uncomment to test actual activation (USE WITH CAUTION!)
        # print("\nTesting zone 1 activation (5 seconds)...")
        # controller.activate_zone(1, duration=5)
        # time.sleep(5)
        # controller.stop_zone(1)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")


if __name__ == "__main__":
    main()
