"""Google Drive integration for training data synchronization."""
import os
import json
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime
import io

from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError


class DriveSync:
    """Handles synchronization of training data with Google Drive."""
    
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    def __init__(self, credentials_path: str, root_folder_id: str):
        """Initialize Drive sync with service account credentials.
        
        Args:
            credentials_path: Path to service account JSON credentials
            root_folder_id: ID of the root folder in Google Drive
        """
        self.credentials_path = Path(credentials_path)
        self.root_folder_id = root_folder_id
        self.service = None
        self._connect()
    
    def _connect(self):
        """Establish connection to Google Drive API using OAuth2 or service account."""
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Credentials file not found: {self.credentials_path}\n"
                f"See docs/GOOGLE_DRIVE_SETUP.md for setup instructions"
            )
        
        try:
            # Check if it's a service account or OAuth2 client credentials
            with open(self.credentials_path, 'r') as f:
                cred_data = json.load(f)
            
            if cred_data.get('type') == 'service_account':
                # Service account (won't work for personal Google Drive)
                print("⚠ Warning: Service accounts don't work with personal Google Drive")
                print("⚠ Please use OAuth2 credentials instead")
                credentials = ServiceAccountCredentials.from_service_account_file(
                    str(self.credentials_path),
                    scopes=self.SCOPES
                )
            else:
                # OAuth2 user credentials
                token_path = self.credentials_path.parent / 'drive_token.json'
                credentials = None
                
                # Load existing token if available
                if token_path.exists():
                    credentials = UserCredentials.from_authorized_user_file(
                        str(token_path),
                        self.SCOPES
                    )
                
                # If no valid credentials, require user to authenticate
                if not credentials or not credentials.valid:
                    if credentials and credentials.expired and credentials.refresh_token:
                        credentials.refresh(Request())
                    else:
                        raise ConnectionError(
                            "OAuth2 token missing or expired. "
                            "Run: python scripts/setup_google_drive_oauth.py"
                        )
                    
                    # Save the refreshed token
                    with open(token_path, 'w') as token_file:
                        token_file.write(credentials.to_json())
            
            self.service = build('drive', 'v3', credentials=credentials)
            
            # Test connection
            self.service.files().get(fileId=self.root_folder_id, supportsAllDrives=True).execute()
            print(f"✓ Connected to Google Drive (folder: {self.root_folder_id})")
            
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to Google Drive: {e}\n"
                f"Check credentials and folder ID in .env file"
            )
    
    def create_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        """Create a folder in Google Drive.
        
        Args:
            name: Folder name
            parent_id: Parent folder ID (uses root if None)
        
        Returns:
            Created folder ID
        """
        parent_id = parent_id or self.root_folder_id
        
        # Check if folder already exists
        query = f"name='{name}' and '{parent_id}' in parents and trashed=false"
        results = self.service.files().list(q=query, fields='files(id, name)', supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        items = results.get('files', [])
        
        if items:
            print(f"✓ Folder '{name}' already exists")
            return items[0]['id']
        
        # Create new folder
        file_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_id]
        }
        
        folder = self.service.files().create(
            body=file_metadata,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        print(f"✓ Created folder '{name}'")
        return folder['id']
    
    def upload_file(
        self,
        local_path: Path,
        drive_folder_id: str,
        filename: Optional[str] = None
    ) -> str:
        """Upload a file to Google Drive.
        
        Args:
            local_path: Path to local file
            drive_folder_id: ID of destination folder
            filename: Optional custom filename (uses local filename if None)
        
        Returns:
            Uploaded file ID
        """
        filename = filename or local_path.name
        
        # Check if file already exists
        query = f"name='{filename}' and '{drive_folder_id}' in parents and trashed=false"
        results = self.service.files().list(q=query, fields='files(id, name)', supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        items = results.get('files', [])
        
        file_metadata = {
            'name': filename,
            'parents': [drive_folder_id]
        }
        
        media = MediaFileUpload(
            str(local_path),
            resumable=True
        )
        
        if items:
            # Update existing file
            file_id = items[0]['id']
            self.service.files().update(
                fileId=file_id,
                media_body=media,
                supportsAllDrives=True
            ).execute()
            print(f"✓ Updated '{filename}'")
        else:
            # Create new file
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id',
                supportsAllDrives=True
            ).execute()
            file_id = file['id']
            print(f"✓ Uploaded '{filename}'")
        
        return file_id
    
    def upload_directory(
        self,
        local_dir: Path,
        drive_folder_id: str,
        exclude_patterns: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Upload an entire directory to Google Drive.
        
        Args:
            local_dir: Path to local directory
            drive_folder_id: ID of destination folder
            exclude_patterns: List of glob patterns to exclude
        
        Returns:
            Dictionary mapping local paths to Drive file IDs
        """
        exclude_patterns = exclude_patterns or []
        uploaded = {}
        
        for item in local_dir.rglob('*'):
            if item.is_file():
                # Check exclusions
                skip = False
                for pattern in exclude_patterns:
                    if item.match(pattern):
                        skip = True
                        break
                
                if skip:
                    continue
                
                # Get relative path for folder structure
                rel_path = item.relative_to(local_dir)
                
                # Create subdirectories as needed
                current_folder_id = drive_folder_id
                if len(rel_path.parts) > 1:
                    for part in rel_path.parts[:-1]:
                        current_folder_id = self.create_folder(part, current_folder_id)
                
                # Upload file
                file_id = self.upload_file(item, current_folder_id)
                uploaded[str(item)] = file_id
        
        print(f"✓ Uploaded {len(uploaded)} files from {local_dir.name}")
        return uploaded
    
    def download_file(
        self,
        file_id: str,
        local_path: Path
    ):
        """Download a file from Google Drive.
        
        Args:
            file_id: Drive file ID
            local_path: Path to save file locally
        """
        request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)
        
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(local_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"  Downloading: {progress}%", end='\r')
        
        print(f"✓ Downloaded to {local_path}")
    
    def list_files(
        self,
        folder_id: str,
        file_type: Optional[str] = None
    ) -> List[Dict]:
        """List files in a Google Drive folder.
        
        Args:
            folder_id: Drive folder ID
            file_type: Optional MIME type filter
        
        Returns:
            List of file metadata dictionaries
        """
        query = f"'{folder_id}' in parents and trashed=false"
        if file_type:
            query += f" and mimeType='{file_type}'"
        
        results = self.service.files().list(
            q=query,
            fields='files(id, name, mimeType, createdTime, modifiedTime)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()
        
        return results.get('files', [])
    
    def sync_training_dataset(
        self,
        local_dataset_dir: Path,
        version: Optional[str] = None
    ) -> str:
        """Sync a training dataset to Google Drive.
        
        Args:
            local_dataset_dir: Path to local dataset directory
            version: Dataset version (uses timestamp if None)
        
        Returns:
            Drive folder ID of uploaded dataset
        """
        version = version or datetime.now().strftime("v%Y%m%d_%H%M%S")
        
        # Create training_data folder if needed
        training_data_id = self.create_folder('training_data')
        
        # Create version folder
        version_folder_id = self.create_folder(version, training_data_id)
        
        # Upload dataset
        self.upload_directory(
            local_dataset_dir,
            version_folder_id,
            exclude_patterns=['*.pyc', '__pycache__', '.DS_Store']
        )
        
        print(f"✓ Synced training dataset {version} to Google Drive")
        return version_folder_id
    
    def get_latest_model(self, local_dir: Path) -> Optional[Path]:
        """Download the latest trained model from Google Drive.
        
        Args:
            local_dir: Path to save model locally
        
        Returns:
            Path to downloaded model, or None if no models found
        """
        # List models in trained_models folder
        models_folder_id = self.create_folder('trained_models')
        models = self.list_files(models_folder_id)
        
        if not models:
            print("No trained models found in Drive")
            return None
        
        # Sort by modification time (newest first)
        models.sort(key=lambda x: x['modifiedTime'], reverse=True)
        latest = models[0]
        
        print(f"Downloading latest model: {latest['name']}")
        local_path = local_dir / latest['name']
        self.download_file(latest['id'], local_path)
        
        return local_path


def test_connection():
    """Test Google Drive connection."""
    from dotenv import load_dotenv
    load_dotenv()
    
    credentials_path = os.getenv('GOOGLE_DRIVE_CREDENTIALS_PATH')
    folder_id = os.getenv('GOOGLE_DRIVE_TRAINING_FOLDER_ID')
    
    if not credentials_path or not folder_id:
        print("❌ Missing environment variables:")
        print("   - GOOGLE_DRIVE_CREDENTIALS_PATH")
        print("   - GOOGLE_DRIVE_TRAINING_FOLDER_ID")
        print("\nSee docs/GOOGLE_DRIVE_SETUP.md for setup instructions")
        return False
    
    try:
        sync = DriveSync(credentials_path, folder_id)
        print("\n✓ Successfully connected to Google Drive")
        
        # List contents
        files = sync.list_files(folder_id)
        print(f"✓ Found {len(files)} items in root folder")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        return False


if __name__ == '__main__':
    test_connection()
