"""
Data download utility for fetching annotated deer images from Google Drive.
"""
import os
import gdown
from pathlib import Path
from typing import Optional
import yaml
from dotenv import load_dotenv

load_dotenv()


class GoogleDriveDownloader:
    """Download annotated images from Google Drive."""
    
    def __init__(self, output_dir: str = "data/raw"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        
    def download_folder(self, folder_id: Optional[str] = None) -> None:
        """
        Download entire folder from Google Drive.
        
        Args:
            folder_id: Google Drive folder ID. If None, uses env variable.
        """
        if folder_id is None:
            folder_id = self.folder_id
            
        if not folder_id:
            raise ValueError(
                "No folder ID provided. Set GOOGLE_DRIVE_FOLDER_ID in .env "
                "or pass folder_id parameter."
            )
        
        print(f"Downloading data from Google Drive folder: {folder_id}")
        print(f"Output directory: {self.output_dir}")
        
        # Download entire folder (with remaining_ok to handle large folders)
        url = f"https://drive.google.com/drive/folders/{folder_id}"
        try:
            gdown.download_folder(
                url=url,
                output=str(self.output_dir),
                quiet=False,
                use_cookies=False,
                remaining_ok=True  # Don't error on 50+ files, just download what we can
            )
        except Exception as e:
            if "more than 50 files" in str(e):
                print("\n⚠ Your folder has more than 50 files.")
                print("gdown has a 50-file limit for public folders.")
                print("\nOptions to download all your data:")
                print("  1. Use Google Drive desktop app to sync the folder")
                print("  2. Manually download and extract to data/raw/")
                print("  3. Set up Google Drive API credentials (see GETTING_STARTED.md)")
                print(f"\nFolder URL: https://drive.google.com/drive/folders/{folder_id}")
                raise
            else:
                raise
        
        print(f"\nDownload complete! Files saved to: {self.output_dir}")
        self._print_summary()
    
    def download_file(self, file_id: str, output_name: str) -> None:
        """
        Download a single file from Google Drive.
        
        Args:
            file_id: Google Drive file ID
            output_name: Name to save the file as
        """
        output_path = self.output_dir / output_name
        url = f"https://drive.google.com/uc?id={file_id}"
        
        print(f"Downloading {output_name}...")
        gdown.download(url, str(output_path), quiet=False)
        print(f"Saved to: {output_path}")
    
    def _print_summary(self) -> None:
        """Print summary of downloaded files."""
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        annotation_extensions = {'.txt', '.xml', '.json'}
        
        images = []
        annotations = []
        
        for file_path in self.output_dir.rglob('*'):
            if file_path.is_file():
                if file_path.suffix.lower() in image_extensions:
                    images.append(file_path)
                elif file_path.suffix.lower() in annotation_extensions:
                    annotations.append(file_path)
        
        print(f"\n{'='*50}")
        print("Download Summary:")
        print(f"  Images found: {len(images)}")
        print(f"  Annotations found: {len(annotations)}")
        print(f"{'='*50}\n")


def main():
    """Main entry point for data download."""
    downloader = GoogleDriveDownloader()
    
    print("Deer Deterrent - Data Download Utility")
    print("=" * 50)
    
    try:
        downloader.download_folder()
        print("\n✓ Data download successful!")
        print("\nNext steps:")
        print("  1. Verify your images and annotations in data/raw/")
        print("  2. Run data preparation: python src/data/prepare_dataset.py")
        print("  3. Begin training: python src/training/train.py")
        
    except Exception as e:
        print(f"\n✗ Error during download: {e}")
        print("\nTroubleshooting:")
        print("  - Ensure GOOGLE_DRIVE_FOLDER_ID is set in .env")
        print("  - Check that the Google Drive folder is shared (anyone with link)")
        print("  - For private folders, set up Google API credentials")
        

if __name__ == "__main__":
    main()
