#!/usr/bin/env python3
"""Upload updated Colab notebook to Google Drive."""

from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configuration
SCOPES = ['https://www.googleapis.com/auth/drive']
FOLDER_ID = '1NUuOhA7rWCiGcxWPe6sOHNnzOKO0zZf5'

def main():
    """Upload notebook to Google Drive."""
    
    project_root = Path(__file__).parent.parent
    token_path = project_root / 'configs' / 'drive_token.json'
    notebook_path = project_root / 'notebooks' / 'train_deer_detector_colab.ipynb'
    
    if not token_path.exists():
        print(f"❌ Token file not found: {token_path}")
        return
    
    if not notebook_path.exists():
        print(f"❌ Notebook not found: {notebook_path}")
        return
    
    # Load credentials
    credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    service = build('drive', 'v3', credentials=credentials)
    
    print("📤 Uploading notebook to Google Drive...")
    
    # Check if file already exists
    query = f"name='train_deer_detector_colab.ipynb' and '{FOLDER_ID}' in parents and trashed=false"
    results = service.files().list(
        q=query,
        fields='files(id, name)',
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    
    existing_files = results.get('files', [])
    
    media = MediaFileUpload(
        str(notebook_path),
        mimetype='application/x-ipynb+json',
        resumable=True
    )
    
    if existing_files:
        # Update existing file
        file_id = existing_files[0]['id']
        print(f"   Updating existing notebook (ID: {file_id})...")
        
        file = service.files().update(
            fileId=file_id,
            media_body=media,
            supportsAllDrives=True
        ).execute()
        
        print(f"✅ Notebook updated successfully!")
    else:
        # Create new file
        print(f"   Creating new notebook...")
        
        file_metadata = {
            'name': 'train_deer_detector_colab.ipynb',
            'parents': [FOLDER_ID]
        }
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        print(f"✅ Notebook uploaded successfully!")
    
    print(f"\n📁 Open in Google Colab:")
    print(f"   https://colab.research.google.com/drive/{file.get('id')}")

if __name__ == '__main__':
    main()
