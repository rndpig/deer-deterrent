#!/usr/bin/env python3
"""Check training data uploaded to Google Drive."""

import json
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# Configuration
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
FOLDER_ID = '1NUuOhA7rWCiGcxWPe6sOHNnzOKO0zZf5'

def main():
    """Check training data in Google Drive."""
    
    project_root = Path(__file__).parent.parent
    token_path = project_root / 'configs' / 'drive_token.json'
    
    if not token_path.exists():
        print(f"❌ Token file not found: {token_path}")
        return
    
    # Load credentials
    credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    service = build('drive', 'v3', credentials=credentials)
    
    print("📂 Checking Google Drive folder...")
    print(f"   Folder ID: {FOLDER_ID}\n")
    
    # List all files in the folder
    results = service.files().list(
        q=f"'{FOLDER_ID}' in parents and trashed=false",
        fields='files(id, name, mimeType, size)',
        supportsAllDrives=True,
        includeItemsFromAllDrives=True
    ).execute()
    
    files = results.get('files', [])
    
    # Organize by type
    folders = [f for f in files if f['mimeType'] == 'application/vnd.google-apps.folder']
    json_files = [f for f in files if f['name'].endswith('.json')]
    other_files = [f for f in files if f not in folders and f not in json_files]
    
    print(f"📁 Folders: {len(folders)}")
    for folder in folders:
        print(f"   - {folder['name']}")
        
        # Count files in this folder
        folder_contents = service.files().list(
            q=f"'{folder['id']}' in parents and trashed=false",
            fields='files(id, name)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        file_count = len(folder_contents.get('files', []))
        print(f"     Contains: {file_count} files")
    
    print(f"\n📄 JSON files: {len(json_files)}")
    for json_file in json_files:
        size_kb = int(json_file.get('size', 0)) / 1024
        print(f"   - {json_file['name']} ({size_kb:.1f} KB)")
    
    if other_files:
        print(f"\n📎 Other files: {len(other_files)}")
        for f in other_files[:5]:
            print(f"   - {f['name']}")
        if len(other_files) > 5:
            print(f"   ... and {len(other_files) - 5} more")
    
    # Download and check annotations.json
    print("\n📊 Checking annotations.json...")
    annotations_file = next((f for f in json_files if f['name'] == 'annotations.json'), None)
    
    if annotations_file:
        # Download the file
        request = service.files().get_media(fileId=annotations_file['id'], supportsAllDrives=True)
        import io
        fh = io.BytesIO()
        from googleapiclient.http import MediaIoBaseDownload
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        
        # Parse JSON
        fh.seek(0)
        data = json.load(fh)
        
        print(f"   Images: {len(data.get('images', []))}")
        print(f"   Annotations: {len(data.get('annotations', []))}")
        print(f"   Categories: {len(data.get('categories', []))}")
        
        # Check for duplicates
        image_filenames = [img['file_name'] for img in data.get('images', [])]
        unique_filenames = set(image_filenames)
        
        if len(image_filenames) != len(unique_filenames):
            duplicates = len(image_filenames) - len(unique_filenames)
            print(f"\n   ⚠️  Found {duplicates} duplicate image references!")
            
            # Show some duplicates
            from collections import Counter
            filename_counts = Counter(image_filenames)
            dupes = [(name, count) for name, count in filename_counts.items() if count > 1]
            print(f"   Sample duplicates:")
            for name, count in dupes[:5]:
                print(f"      - {name} appears {count} times")
        else:
            print(f"   ✓ No duplicate image references")
        
        # Check if image files match annotations
        print(f"\n   Verifying image files exist in Drive...")
        images_folder = next((f for f in folders if f['name'] == 'images'), None)
        if images_folder:
            drive_images = service.files().list(
                q=f"'{images_folder['id']}' in parents and trashed=false",
                fields='files(name)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageSize=1000
            ).execute()
            
            drive_image_names = set(f['name'] for f in drive_images.get('files', []))
            expected_images = set(image_filenames)
            
            print(f"   Expected images: {len(expected_images)}")
            print(f"   Actual images in Drive: {len(drive_image_names)}")
            
            missing = expected_images - drive_image_names
            extra = drive_image_names - expected_images
            
            if missing:
                print(f"   ⚠️  Missing {len(missing)} images from Drive")
            if extra:
                print(f"   ⚠️  Found {len(extra)} extra images in Drive")
            if not missing and not extra:
                print(f"   ✓ All images match!")
    
    print("\n✅ Drive check complete!")

if __name__ == '__main__':
    main()
