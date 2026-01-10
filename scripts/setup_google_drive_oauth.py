#!/usr/bin/env python3
"""Setup OAuth2 credentials for Google Drive access."""

import json
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Scopes required for Drive access
SCOPES = ['https://www.googleapis.com/auth/drive']

def setup_oauth():
    """Run OAuth2 flow to get user credentials."""
    
    project_root = Path(__file__).parent.parent
    credentials_path = project_root / 'configs' / 'google-credentials.json'
    token_path = project_root / 'configs' / 'drive_token.json'
    
    if not credentials_path.exists():
        print(f"❌ Credentials file not found: {credentials_path}")
        print("\n📋 Follow these steps:")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Create OAuth 2.0 Client ID (Desktop application)")
        print("3. Download the JSON file")
        print(f"4. Save it as: {credentials_path}")
        return
    
    # Check if it's OAuth2 credentials (not service account)
    with open(credentials_path, 'r') as f:
        cred_data = json.load(f)
    
    if cred_data.get('type') == 'service_account':
        print("❌ This is a service account credential file")
        print("⚠️  Service accounts don't work with personal Google Drive folders")
        print("\n📋 You need OAuth 2.0 Client ID credentials:")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Click 'Create Credentials' → 'OAuth 2.0 Client ID'")
        print("3. Application type: 'Desktop application'")
        print("4. Name: 'Deer Deterrent Training'")
        print("5. Download the JSON file")
        print(f"6. Save it as: {credentials_path}")
        print("\n💡 Keep the service account file for reference:")
        backup_path = credentials_path.parent / 'google-credentials-service-account.json'
        print(f"   mv {credentials_path} {backup_path}")
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
        print("✅ You can now upload to Google Drive using your personal account")
        print("\n🔒 Keep these files secure:")
        print(f"   - {credentials_path}")
        print(f"   - {token_path}")
        
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        return

if __name__ == '__main__':
    setup_oauth()
