#!/usr/bin/env python3
"""Setup OAuth2 credentials for Google Drive access - runs locally then copies token to server."""

import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import subprocess

# Scopes required for Drive access
SCOPES = ['https://www.googleapis.com/auth/drive']

def setup_oauth():
    """Run OAuth2 flow to get user credentials."""
    
    project_root = Path(__file__).parent.parent
    credentials_path = project_root / 'configs' / 'google-credentials.json'
    token_path = project_root / 'configs' / 'drive_token.json'
    
    if not credentials_path.exists():
        print(f"❌ Credentials file not found: {credentials_path}")
        print("\n📋 Download OAuth2 credentials from Google Cloud Console")
        return
    
    # Check if it's OAuth2 credentials (not service account)
    with open(credentials_path, 'r') as f:
        cred_data = json.load(f)
    
    if cred_data.get('type') == 'service_account':
        print("❌ This is a service account credential file")
        print("⚠️  You need OAuth 2.0 Client ID credentials (Desktop app)")
        return
    
    print("🔐 Starting OAuth2 authentication flow...")
    print("📝 A browser window will open for you to authorize access")
    
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(credentials_path),
            SCOPES
        )
        
        # Run local server to complete OAuth flow
        credentials = flow.run_local_server(port=0)
        
        # Save the credentials for future use
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, 'w') as token_file:
            token_file.write(credentials.to_json())
        
        print(f"\n✅ Success! Token saved to: {token_path}")
        print("\n📤 Now copying token to server...")
        
        # Copy token to server
        try:
            result = subprocess.run(
                ['scp', str(token_path), 'dilger:/home/rndpig/deer-deterrent/configs/drive_token.json'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("✅ Token copied to server successfully!")
                print("\n🎉 Setup complete! You can now use the Train Model button.")
                print("\n🔒 Keep these files secure:")
                print(f"   - {credentials_path}")
                print(f"   - {token_path}")
            else:
                print(f"❌ Failed to copy token to server: {result.stderr}")
                print(f"\n⚠️  Manually copy the token:")
                print(f"   scp {token_path} dilger:/home/rndpig/deer-deterrent/configs/drive_token.json")
        except FileNotFoundError:
            print(f"\n⚠️  scp not found. Manually copy the token:")
            print(f"   scp {token_path} dilger:/home/rndpig/deer-deterrent/configs/drive_token.json")
        
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        return

if __name__ == '__main__':
    setup_oauth()
