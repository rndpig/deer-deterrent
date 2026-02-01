"""
Cloudflare R2 storage integration for backup and training data.
S3-compatible API using boto3.
"""
import boto3
from botocore.exceptions import ClientError
from pathlib import Path
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
import os

logger = logging.getLogger(__name__)


class R2Storage:
    """Handles backup and sync to Cloudflare R2 storage."""
    
    def __init__(self, account_id: str, access_key_id: str, secret_access_key: str, bucket_name: str):
        """
        Initialize R2 storage client.
        
        Args:
            account_id: Cloudflare account ID
            access_key_id: R2 access key ID
            secret_access_key: R2 secret access key
            bucket_name: R2 bucket name
        """
        self.account_id = account_id
        self.bucket_name = bucket_name
        
        # R2 endpoint format: https://<account_id>.r2.cloudflarestorage.com
        endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name='auto'  # R2 uses 'auto' region
        )
        
        logger.info(f"Initialized R2 storage client for bucket: {bucket_name}")
    
    def upload_file(self, local_path: Path, remote_key: str, metadata: Dict = None) -> bool:
        """
        Upload a file to R2.
        
        Args:
            local_path: Local file path
            remote_key: Remote object key (path in bucket)
            metadata: Optional metadata dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = {k: str(v) for k, v in metadata.items()}
            
            self.s3_client.upload_file(
                str(local_path),
                self.bucket_name,
                remote_key,
                ExtraArgs=extra_args
            )
            logger.info(f"Uploaded {local_path.name} to R2: {remote_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to upload {local_path} to R2: {e}")
            return False
    
    def upload_snapshot_with_metadata(self, snapshot_path: Path, event_data: Dict) -> bool:
        """
        Upload a snapshot with its metadata as a separate JSON file.
        
        Args:
            snapshot_path: Local snapshot file path
            event_data: Dictionary containing event metadata (from database)
            
        Returns:
            True if both files uploaded successfully
        """
        # Extract timestamp from event data for folder structure
        timestamp = datetime.fromisoformat(event_data['timestamp'])
        year_month = timestamp.strftime('%Y/%m')
        
        # Upload image
        image_key = f"snapshots/{year_month}/{snapshot_path.name}"
        image_success = self.upload_file(
            snapshot_path,
            image_key,
            metadata={
                'event_id': event_data['id'],
                'camera_id': event_data['camera_id'],
                'timestamp': event_data['timestamp'],
                'deer_detected': str(event_data.get('deer_detected', 0))
            }
        )
        
        if not image_success:
            return False
        
        # Upload metadata JSON
        metadata_key = f"snapshots/{year_month}/{snapshot_path.stem}.json"
        metadata_content = json.dumps(event_data, indent=2)
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=metadata_key,
                Body=metadata_content.encode('utf-8'),
                ContentType='application/json'
            )
            logger.info(f"Uploaded metadata to R2: {metadata_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to upload metadata to R2: {e}")
            return False
    
    def sync_snapshots_batch(self, snapshots: List[Dict], snapshot_dir: Path) -> Dict[str, int]:
        """
        Sync a batch of snapshots to R2.
        
        Args:
            snapshots: List of snapshot event dictionaries from database
            snapshot_dir: Base directory containing snapshot files
            
        Returns:
            Dictionary with counts: {'uploaded': N, 'failed': M, 'skipped': K}
        """
        results = {'uploaded': 0, 'failed': 0, 'skipped': 0}
        
        for event in snapshots:
            if not event.get('snapshot_path'):
                results['skipped'] += 1
                continue
            
            # Resolve snapshot path
            snapshot_path = Path(event['snapshot_path'])
            if not snapshot_path.is_absolute():
                snapshot_path = snapshot_dir / snapshot_path.name
            
            if not snapshot_path.exists():
                logger.warning(f"Snapshot file not found: {snapshot_path}")
                results['skipped'] += 1
                continue
            
            # Upload with metadata
            if self.upload_snapshot_with_metadata(snapshot_path, event):
                results['uploaded'] += 1
            else:
                results['failed'] += 1
        
        logger.info(f"Batch sync complete: {results}")
        return results
    
    def check_if_exists(self, remote_key: str) -> bool:
        """
        Check if an object exists in R2.
        
        Args:
            remote_key: Remote object key
            
        Returns:
            True if exists, False otherwise
        """
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=remote_key)
            return True
        except ClientError:
            return False
    
    def list_objects(self, prefix: str = '', max_keys: int = 1000) -> List[Dict]:
        """
        List objects in bucket with given prefix.
        
        Args:
            prefix: Object key prefix to filter by
            max_keys: Maximum number of objects to return
            
        Returns:
            List of object metadata dictionaries
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            if 'Contents' not in response:
                return []
            
            return [
                {
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified']
                }
                for obj in response['Contents']
            ]
            
        except ClientError as e:
            logger.error(f"Failed to list objects: {e}")
            return []
    
    def export_database(self, db_data: Dict, name: str = None) -> bool:
        """
        Export database data as JSON to R2.
        
        Args:
            db_data: Database export dictionary
            name: Optional custom name, defaults to timestamped export
            
        Returns:
            True if successful
        """
        if name is None:
            name = f"training_db_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        remote_key = f"database-exports/{name}"
        content = json.dumps(db_data, indent=2)
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=remote_key,
                Body=content.encode('utf-8'),
                ContentType='application/json'
            )
            logger.info(f"Exported database to R2: {remote_key}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to export database: {e}")
            return False


def get_r2_client() -> Optional[R2Storage]:
    """
    Get R2 storage client from environment variables.
    
    Environment variables required:
        R2_ACCOUNT_ID
        R2_ACCESS_KEY_ID
        R2_SECRET_ACCESS_KEY
        R2_BUCKET_NAME
    
    Returns:
        R2Storage instance or None if credentials missing
    """
    account_id = os.getenv('R2_ACCOUNT_ID')
    access_key_id = os.getenv('R2_ACCESS_KEY_ID')
    secret_access_key = os.getenv('R2_SECRET_ACCESS_KEY')
    bucket_name = os.getenv('R2_BUCKET_NAME', 'deer-deterrent-backup')
    
    if not all([account_id, access_key_id, secret_access_key]):
        logger.warning("R2 credentials not found in environment variables")
        return None
    
    return R2Storage(account_id, access_key_id, secret_access_key, bucket_name)
