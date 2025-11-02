"""
Test script to discover Rain Bird ESP-Me cloud API endpoints.
The ESP-Me connects to Rain Bird's cloud service, and we need to find
the correct API endpoints by inspecting the mobile app's network traffic.

For now, this script will attempt common API patterns.
"""
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def test_rainbird_api():
    """Test various Rain Bird API endpoints."""
    email = os.getenv("RAINBIRD_EMAIL")
    password = os.getenv("RAINBIRD_PASSWORD")
    
    print("=" * 60)
    print("Rain Bird ESP-Me API Discovery")
    print("=" * 60)
    print(f"\nEmail: {email}")
    print("Password: ***\n")
    
    # Common Rain Bird API base URLs
    base_urls = [
        "https://api.rainbird.com",
        "https://app.rainbird.com/api",
        "https://rainbird.wifisolution.com/api",
        "https://api.rainbird.com/v1",
        "https://api.rainbird.com/v2"
    ]
    
    # Try authentication endpoints
    auth_paths = [
        "/auth/login",
        "/login",
        "/user/login",
        "/authentication/login",
        "/oauth/token",
        "/auth/token"
    ]
    
    print("Testing authentication endpoints...")
    print("-" * 60)
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "RainBird/2.19.7 (iOS)",
        "Content-Type": "application/json",
        "Accept": "application/json"
    })
    
    for base_url in base_urls:
        for auth_path in auth_paths:
            url = f"{base_url}{auth_path}"
            
            # Try different authentication payloads
            payloads = [
                {"email": email, "password": password},
                {"username": email, "password": password},
                {"user": email, "pass": password},
                {"grant_type": "password", "username": email, "password": password}
            ]
            
            for i, payload in enumerate(payloads):
                try:
                    print(f"\nTrying: {url}")
                    print(f"Payload {i+1}: {list(payload.keys())}")
                    
                    response = session.post(
                        url,
                        json=payload,
                        timeout=5
                    )
                    
                    print(f"Status: {response.status_code}")
                    
                    if response.status_code in [200, 201]:
                        print("✓ SUCCESS!")
                        print(f"Response: {response.text[:500]}")
                        
                        # Try to parse and save token
                        try:
                            data = response.json()
                            if 'token' in data or 'access_token' in data:
                                print("\n✓✓ FOUND API ENDPOINT!")
                                print(f"Base URL: {base_url}")
                                print(f"Auth Path: {auth_path}")
                                print(f"Payload: {payload}")
                                return base_url, auth_path, data
                        except:
                            pass
                    elif response.status_code == 404:
                        print("  → Not found")
                    elif response.status_code == 401:
                        print("  → Unauthorized (endpoint exists, but auth failed)")
                    elif response.status_code == 400:
                        print("  → Bad request (endpoint might exist, wrong payload)")
                        print(f"  Response: {response.text[:200]}")
                    else:
                        print(f"  → Status {response.status_code}")
                        
                except requests.exceptions.Timeout:
                    print("  → Timeout")
                except requests.exceptions.ConnectionError:
                    print("  → Connection error")
                except Exception as e:
                    print(f"  → Error: {type(e).__name__}")
    
    print("\n" + "=" * 60)
    print("No working endpoint found automatically.")
    print("\nNext steps:")
    print("1. Install Rain Bird app on phone")
    print("2. Use network monitoring (Charles Proxy / mitmproxy)")
    print("3. Capture actual API calls the app makes")
    print("4. Or check if Rain Bird has official API documentation")
    print("=" * 60)
    
    return None, None, None


def manual_api_test():
    """
    If you've captured the API details from the Rain Bird app,
    enter them here to test.
    """
    print("\n" + "=" * 60)
    print("Manual API Test")
    print("=" * 60)
    
    # If you know the API details, fill them in here:
    API_BASE = ""  # e.g., "https://api.rainbird.com/v1"
    AUTH_ENDPOINT = ""  # e.g., "/auth/login"
    
    if not API_BASE or not AUTH_ENDPOINT:
        print("No manual API details provided.")
        print("\nTo use this, capture the API calls from the Rain Bird app:")
        print("1. Set up a proxy (Charles/Fiddler/mitmproxy)")
        print("2. Configure phone to use proxy")
        print("3. Open Rain Bird app and log in")
        print("4. Capture the authentication request")
        print("5. Fill in API_BASE and AUTH_ENDPOINT above")
        return
    
    # Test with captured details
    email = os.getenv("RAINBIRD_EMAIL")
    password = os.getenv("RAINBIRD_PASSWORD")
    
    response = requests.post(
        f"{API_BASE}{AUTH_ENDPOINT}",
        json={"email": email, "password": password},
        headers={
            "Content-Type": "application/json",
            "User-Agent": "RainBird/2.19.7 (iOS)"
        }
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")


if __name__ == "__main__":
    print("\nStarting Rain Bird API discovery...\n")
    
    # Try automatic discovery
    base_url, auth_path, data = test_rainbird_api()
    
    if base_url:
        print("\n✓ Successfully connected to Rain Bird API!")
        print(f"\nSave these details:")
        print(f"  Base URL: {base_url}")
        print(f"  Auth Path: {auth_path}")
        with open("rainbird_api_config.json", "w") as f:
            json.dump({
                "base_url": base_url,
                "auth_path": auth_path,
                "sample_response": data
            }, f, indent=2)
        print(f"\n✓ Saved to rainbird_api_config.json")
    else:
        # Try manual test if automatic fails
        manual_api_test()
