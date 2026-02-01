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
                # Path is relative - join with snapshot_dir
                snapshot_path = snapshot_dir / event['snapshot_path']
            
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
    
    def clear_bucket(self) -> Dict:
        """
        Delete all objects in the bucket.
        
        Returns:
            Dictionary with deletion results
        """
        results = {'deleted': 0, 'failed': 0}
        
        try:
            # List all objects
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name)
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                
                # Delete objects in batches
                objects = [{'Key': obj['Key']} for obj in page['Contents']]
                
                response = self.s3_client.delete_objects(
                    Bucket=self.bucket_name,
                    Delete={'Objects': objects}
                )
                
                results['deleted'] += len(response.get('Deleted', []))
                results['failed'] += len(response.get('Errors', []))
            
            logger.info(f"Cleared R2 bucket: {results}")
            return results
            
        except ClientError as e:
            logger.error(f"Failed to clear bucket: {e}")
            results['failed'] += 1
            return results


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


def sync_training_data(db, r2_client: R2Storage, base_dir: Path) -> Dict:
    """
    Sync all training-relevant data to R2.
    
    Training data includes:
    - Manual uploads
    - Deer detections
    - False positives marked by user
    - Weekly background samples
    - All original videos
    - All video frames (annotated and unannotated)
    
    Args:
        db: Database instance
        r2_client: R2Storage client
        base_dir: Base directory for file paths (usually /app)
        
    Returns:
        Dictionary with sync results
    """
    results = {
        'snapshots': {'uploaded': 0, 'skipped': 0, 'failed': 0},
        'videos': {'uploaded': 0, 'skipped': 0, 'failed': 0},
        'frames': {'uploaded': 0, 'skipped': 0, 'failed': 0}
    }
    
    # 1. Sync training-relevant snapshots
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Get snapshots that are training-relevant
    cursor.execute("""
        SELECT * FROM ring_events 
        WHERE snapshot_path IS NOT NULL
        AND (
            event_type = 'manual_upload' OR
            deer_detected = 1 OR
            false_positive = 1 OR
            event_type = 'weekly_background_sample'
        )
        AND archived = 0
    """)
    
    snapshots = [dict(row) for row in cursor.fetchall()]
    logger.info(f"Found {len(snapshots)} training snapshots to sync")
    
    for snapshot in snapshots:
        snapshot_path = Path(snapshot['snapshot_path'])
        if not snapshot_path.is_absolute():
            snapshot_path = base_dir / snapshot_path
        
        if not snapshot_path.exists():
            logger.warning(f"Snapshot file not found: {snapshot_path}")
            results['snapshots']['failed'] += 1
            continue
        
        # Check if already exists in R2
        timestamp = datetime.fromisoformat(snapshot['timestamp'])
        year_month = timestamp.strftime('%Y/%m')
        remote_key = f"snapshots/{year_month}/{snapshot_path.name}"
        
        try:
            r2_client.s3_client.head_object(Bucket=r2_client.bucket_name, Key=remote_key)
            results['snapshots']['skipped'] += 1
            continue
        except ClientError:
            pass  # Object doesn't exist, upload it
        
        # Upload snapshot
        if r2_client.upload_snapshot_with_metadata(snapshot_path, snapshot):
            results['snapshots']['uploaded'] += 1
        else:
            results['snapshots']['failed'] += 1
    
    # 2. Sync all videos
    cursor.execute("SELECT * FROM videos WHERE video_path IS NOT NULL")
    videos = [dict(row) for row in cursor.fetchall()]
    logger.info(f"Found {len(videos)} videos to sync")
    
    for video in videos:
        video_path = Path(video['video_path'])
        if not video_path.is_absolute():
            video_path = base_dir / video_path
        
        if not video_path.exists():
            logger.warning(f"Video file not found: {video_path}")
            results['videos']['failed'] += 1
            continue
        
        # Organize by upload date
        upload_date = datetime.fromisoformat(video['upload_date'])
        year_month = upload_date.strftime('%Y/%m')
        remote_key = f"videos/{year_month}/{video_path.name}"
        
        try:
            r2_client.s3_client.head_object(Bucket=r2_client.bucket_name, Key=remote_key)
            results['videos']['skipped'] += 1
            continue
        except ClientError:
            pass
        
        # Upload video with metadata
        metadata = {
            'video_id': video['id'],
            'camera': video.get('camera', 'unknown'),
            'upload_date': video['upload_date'],
            'duration': str(video.get('duration_seconds', 0))
        }
        
        if r2_client.upload_file(video_path, remote_key, metadata):
            results['videos']['uploaded'] += 1
        else:
            results['videos']['failed'] += 1
    
    # 3. Sync all video frames
    cursor.execute("""
        SELECT f.*, v.upload_date as video_upload_date 
        FROM frames f
        JOIN videos v ON f.video_id = v.id
        WHERE f.image_path IS NOT NULL
    """)
    frames = [dict(row) for row in cursor.fetchall()]
    logger.info(f"Found {len(frames)} frames to sync")
    
    for frame in frames:
        frame_path = Path(frame['image_path'])
        if not frame_path.is_absolute():
            frame_path = base_dir / frame_path
        
        if not frame_path.exists():
            logger.warning(f"Frame file not found: {frame_path}")
            results['frames']['failed'] += 1
            continue
        
        # Organize by video upload date
        upload_date = datetime.fromisoformat(frame['video_upload_date'])
        year_month = upload_date.strftime('%Y/%m')
        remote_key = f"frames/{year_month}/{frame_path.name}"
        
        try:
            r2_client.s3_client.head_object(Bucket=r2_client.bucket_name, Key=remote_key)
            results['frames']['skipped'] += 1
            continue
        except ClientError:
            pass
        
        # Upload frame with metadata
        metadata = {
            'frame_id': frame['id'],
            'video_id': frame['video_id'],
            'frame_number': frame['frame_number'],
            'has_deer': str(frame.get('has_deer', 0)),
            'selected_for_training': str(frame.get('selected_for_training', 0))
        }
        
        if r2_client.upload_file(frame_path, remote_key, metadata):
            results['frames']['uploaded'] += 1
        else:
            results['frames']['failed'] += 1
    
    conn.close()
    
    logger.info(f"Sync complete: {results}")
    return results

