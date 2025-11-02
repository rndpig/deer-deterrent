"""
Helper script to authenticate with Ring and handle 2FA.
Run this once to generate an authentication token that can be reused.
"""
import os
from pathlib import Path
from ring_doorbell import Auth
from dotenv import load_dotenv

load_dotenv()

def authenticate_ring():
    """Interactive authentication with 2FA support."""
    print("=" * 60)
    print("Ring Authentication Setup (with 2FA)")
    print("=" * 60)
    
    username = os.getenv("RING_USERNAME")
    password = os.getenv("RING_PASSWORD")
    
    if not username or not password:
        print("Error: RING_USERNAME and RING_PASSWORD must be set in .env file")
        return
    
    print(f"\nUsername: {username}")
    print("Password: ***")
    
    cache_file = Path("ring_token.cache")
    
    try:
        # Pass cache_file as string, not Path object
        auth = Auth("DeerDeterrent/1.0", None, str(cache_file))
        
        print("\nAttempting to authenticate...")
        print("(A 2FA code will be sent to your phone/email)")
        
        # This will trigger 2FA
        auth.fetch_token(username, password)
        
        # If we get here without error, 2FA was successful
        print("\n✓ Authentication successful!")
        print(f"✓ Token saved to: {cache_file}")
        print("\nYou can now run the main application without entering 2FA again.")
        print("The token will be automatically refreshed as needed.")
        
    except Exception as e:
        error_msg = str(e)
        
        if "2FA" in error_msg or "Requires2FA" in str(type(e)):
            print("\n2FA Required:")
            print("1. Check your phone/email for a Ring 2FA code")
            print("2. Enter the code when prompted")
            
            # Get 2FA code from user
            code = input("\nEnter 2FA code: ").strip()
            
            try:
                # Fetch token with 2FA code
                auth.fetch_token(username, password, code)
                
                print("\n✓ Authentication successful!")
                print(f"✓ Token saved to: {cache_file}")
                print("\nYou can now run the main application.")
                
            except Exception as e2:
                print(f"\n✗ 2FA failed: {e2}")
                import traceback
                traceback.print_exc()
                print("\nTroubleshooting:")
                print("  - Make sure you entered the code quickly (they expire)")
                print("  - Try running this script again to get a fresh code")
        else:
            print(f"\n✗ Authentication failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    authenticate_ring()
