"""
SQLite database for persistent storage of training data.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

DB_PATH = Path("data/training.db")

def init_database():
    """Initialize the database with required tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    cursor = conn.cursor()
    
    # Videos table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            upload_date TEXT NOT NULL,
            camera_name TEXT,
            duration_seconds REAL,
            fps REAL,
            total_frames INTEGER,
            status TEXT DEFAULT 'analyzed',
            video_path TEXT,
            archived BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    
    # Frames table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS frames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            frame_number INTEGER NOT NULL,
            timestamp_in_video REAL,
            image_path TEXT NOT NULL,
            has_detections BOOLEAN DEFAULT 0,
            reviewed BOOLEAN DEFAULT 0,
            review_type TEXT,
            selected_for_training BOOLEAN DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        )
    """)
    
    # Auto-detections from YOLO
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            frame_id INTEGER NOT NULL,
            bbox_x1 REAL NOT NULL,
            bbox_y1 REAL NOT NULL,
            bbox_x2 REAL NOT NULL,
            bbox_y2 REAL NOT NULL,
            confidence REAL NOT NULL,
            class_name TEXT DEFAULT 'deer',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (frame_id) REFERENCES frames(id) ON DELETE CASCADE
        )
    """)
    
    # Manual annotations (corrections and additions)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            frame_id INTEGER NOT NULL,
            bbox_x REAL NOT NULL,
            bbox_y REAL NOT NULL,
            bbox_width REAL NOT NULL,
            bbox_height REAL NOT NULL,
            annotation_type TEXT DEFAULT 'addition',
            annotator TEXT DEFAULT 'user',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (frame_id) REFERENCES frames(id) ON DELETE CASCADE
        )
    """)
    
    # Training sessions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS training_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_count INTEGER NOT NULL,
            frame_count INTEGER NOT NULL,
            annotation_count INTEGER NOT NULL,
            exported BOOLEAN DEFAULT 0,
            export_path TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    
    # Ring events log (for diagnostics)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ring_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            snapshot_available BOOLEAN DEFAULT 0,
            snapshot_size INTEGER,
            snapshot_path TEXT,
            recording_url TEXT,
            processed BOOLEAN DEFAULT 0,
            deer_detected BOOLEAN,
            detection_confidence REAL,
            error_message TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    
    # Create indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_frames_video ON frames(video_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_frames_training ON frames(selected_for_training)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_detections_frame ON detections(frame_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_annotations_frame ON annotations(frame_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ring_events_camera ON ring_events(camera_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ring_events_timestamp ON ring_events(timestamp)")
    
    # Migration: Add camera and captured_at columns if they don't exist
    cursor.execute("PRAGMA table_info(videos)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'camera' not in columns:
        cursor.execute("ALTER TABLE videos ADD COLUMN camera TEXT")
        print("✓ Added 'camera' column to videos table")
        logger.info("Added 'camera' column to videos table")
    
    if 'captured_at' not in columns:
        cursor.execute("ALTER TABLE videos ADD COLUMN captured_at TEXT")
        print("✓ Added 'captured_at' column to videos table")
        logger.info("Added 'captured_at' column to videos table")
    
    if 'archived' not in columns:
        cursor.execute("ALTER TABLE videos ADD COLUMN archived BOOLEAN DEFAULT 0")
        print("✓ Added 'archived' column to videos table")
        logger.info("Added 'archived' column to videos table")
    
    # Migration: Add archived column to ring_events if it doesn't exist
    cursor.execute("PRAGMA table_info(ring_events)")
    ring_columns = [row[1] for row in cursor.fetchall()]
    
    if 'archived' not in ring_columns:
        cursor.execute("ALTER TABLE ring_events ADD COLUMN archived BOOLEAN DEFAULT 0")
        print("✓ Added 'archived' column to ring_events table")
        logger.info("Added 'archived' column to ring_events table")
    
    conn.commit()
    conn.close()
    
    logger.info(f"Database initialized at {DB_PATH}")

def get_connection():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Video operations
def add_video(filename: str, camera_name: str, duration: float, fps: float, 
              total_frames: int, video_path: str) -> int:
    """Add a new video to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO videos (filename, upload_date, camera_name, duration_seconds, 
                          fps, total_frames, video_path)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (filename, datetime.now().isoformat(), camera_name, duration, fps, total_frames, video_path))
    
    video_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return video_id

def get_all_videos() -> List[Dict]:
    """Get all non-archived videos with frame and detection counts."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            v.*,
            COUNT(DISTINCT f.id) as frame_count,
            COUNT(DISTINCT d.id) as detection_count,
            COUNT(DISTINCT a.id) as annotation_count
        FROM videos v
        LEFT JOIN frames f ON v.id = f.video_id
        LEFT JOIN detections d ON f.id = d.frame_id
        LEFT JOIN annotations a ON f.id = a.frame_id
        WHERE v.archived = 0 OR v.archived IS NULL
        GROUP BY v.id
        ORDER BY v.created_at DESC
    """)
    
    videos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return videos

def video_has_annotations(video_id: int) -> bool:
    """Check if a video has any manual annotations on its frames."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM annotations a
        JOIN frames f ON a.frame_id = f.id
        WHERE f.video_id = ?
    """, (video_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    return result['count'] > 0 if result else False

def video_fully_annotated(video_id: int) -> bool:
    """Check if ALL frames from a video have been annotated or reviewed."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get count of frames selected for training
    cursor.execute("""
        SELECT COUNT(*) as total
        FROM frames
        WHERE video_id = ? AND selected_for_training = 1
    """, (video_id,))
    
    total_result = cursor.fetchone()
    total_frames = total_result['total'] if total_result else 0
    
    if total_frames == 0:
        conn.close()
        return False
    
    # Get count of frames that have annotations OR are reviewed
    cursor.execute("""
        SELECT COUNT(DISTINCT f.id) as annotated
        FROM frames f
        LEFT JOIN annotations a ON f.id = a.frame_id
        WHERE f.video_id = ? 
          AND f.selected_for_training = 1
          AND (a.id IS NOT NULL OR f.reviewed = 1)
    """, (video_id,))
    
    annotated_result = cursor.fetchone()
    annotated_frames = annotated_result['annotated'] if annotated_result else 0
    
    conn.close()
    
    return annotated_frames >= total_frames

def get_video(video_id: int) -> Optional[Dict]:
    """Get a specific video with details."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
    row = cursor.fetchone()
    
    if row:
        video = dict(row)
        conn.close()
        return video
    
    conn.close()
    return None

def archive_video(video_id: int) -> bool:
    """Archive a video (sets archived=1)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE videos 
        SET archived = 1
        WHERE id = ?
    """, (video_id,))
    
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    
    return success

def unarchive_video(video_id: int) -> bool:
    """Unarchive a video (sets archived=0)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE videos 
        SET archived = 0
        WHERE id = ?
    """, (video_id,))
    
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    
    return success

def get_archived_videos() -> List[Dict]:
    """Get all archived videos with frame and detection counts."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            v.*,
            COUNT(DISTINCT f.id) as frame_count,
            COUNT(DISTINCT d.id) as detection_count,
            COUNT(DISTINCT a.id) as annotation_count
        FROM videos v
        LEFT JOIN frames f ON v.id = f.video_id
        LEFT JOIN detections d ON f.id = d.frame_id
        LEFT JOIN annotations a ON f.id = a.frame_id
        WHERE v.archived = 1
        GROUP BY v.id
        ORDER BY v.created_at DESC
    """)
    
    videos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return videos

def update_video_camera_name(video_id: int, camera_name: str) -> bool:
    """Update the camera name for a video."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE videos 
        SET camera_name = ? 
        WHERE id = ?
    """, (camera_name, video_id))
    
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return updated

def delete_video(video_id: int) -> bool:
    """Delete a video and all associated frames/detections/annotations."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
    deleted = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return deleted

def update_video_metadata(video_id: int, camera: str = None, captured_at: str = None) -> bool:
    """Update video metadata (camera and/or captured_at timestamp)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if camera is not None:
        updates.append("camera = ?")
        params.append(camera)
    
    if captured_at is not None:
        updates.append("captured_at = ?")
        params.append(captured_at)
    
    if not updates:
        conn.close()
        return False
    
    query = f"UPDATE videos SET {', '.join(updates)} WHERE id = ?"
    params.append(video_id)
    
    cursor.execute(query, params)
    updated = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return updated

def get_video_count() -> int:
    """Get total number of videos."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as count FROM videos")
    count = cursor.fetchone()['count']
    
    conn.close()
    return count

# Frame operations
def add_frame(video_id: int, frame_number: int, timestamp_in_video: float, 
              image_path: str, has_detections: bool = False) -> int:
    """Add a new frame to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO frames (video_id, frame_number, timestamp_in_video, image_path, has_detections)
        VALUES (?, ?, ?, ?, ?)
    """, (video_id, frame_number, timestamp_in_video, image_path, has_detections))
    
    frame_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return frame_id

def delete_frame(frame_id: int) -> bool:
    """Delete a frame and its associated detections and annotations."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Delete associated detections
    cursor.execute("DELETE FROM detections WHERE frame_id = ?", (frame_id,))
    
    # Delete associated annotations  
    cursor.execute("DELETE FROM annotations WHERE frame_id = ?", (frame_id,))
    
    # Delete the frame
    cursor.execute("DELETE FROM frames WHERE id = ?", (frame_id,))
    
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return deleted

def get_frames_for_video(video_id: int) -> List[Dict]:
    """Get all frames for a specific video."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT f.*, 
               COUNT(DISTINCT d.id) as detection_count,
               COUNT(DISTINCT a.id) as annotation_count
        FROM frames f
        LEFT JOIN detections d ON f.id = d.frame_id
        LEFT JOIN annotations a ON f.id = a.frame_id
        WHERE f.video_id = ?
        GROUP BY f.id
        ORDER BY f.frame_number
    """, (video_id,))
    
    frames = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return frames

def get_frame(frame_id: int) -> Optional[Dict]:
    """Get a specific frame with detections and annotations."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM frames WHERE id = ?", (frame_id,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return None
    
    frame = dict(row)
    
    # Get detections
    cursor.execute("SELECT * FROM detections WHERE frame_id = ?", (frame_id,))
    frame['detections'] = [dict(r) for r in cursor.fetchall()]
    
    # Get annotations
    cursor.execute("SELECT * FROM annotations WHERE frame_id = ?", (frame_id,))
    frame['annotations'] = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return frame

def update_frame_review(frame_id: int, reviewed: bool, review_type: Optional[str] = None):
    """Update frame review status."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE frames 
        SET reviewed = ?, review_type = ?
        WHERE id = ?
    """, (reviewed, review_type, frame_id))
    
    conn.commit()
    conn.close()

def mark_frame_for_training(frame_id: int):
    """Mark a frame as selected for training review."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE frames 
        SET selected_for_training = 1
        WHERE id = ?
    """, (frame_id,))
    
    conn.commit()
    conn.close()

def unmark_frame_for_training(frame_id: int):
    """Remove training selection flag from a frame."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE frames 
        SET selected_for_training = 0
        WHERE id = ?
    """, (frame_id,))
    
    conn.commit()
    conn.close()

def get_training_frames() -> List[Dict]:
    """Get all frames selected for training."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT f.*, v.filename, v.camera_name
        FROM frames f
        JOIN videos v ON f.video_id = v.id
        WHERE f.selected_for_training = 1
        ORDER BY f.id
    """)
    
    frames = [dict(row) for row in cursor.fetchall()]
    
    # Get detections and annotations for each frame
    for frame in frames:
        cursor.execute("SELECT * FROM detections WHERE frame_id = ?", (frame['id'],))
        frame['detections'] = [dict(r) for r in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM annotations WHERE frame_id = ?", (frame['id'],))
        frame['annotations'] = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return frames

# Detection operations
def add_detection(frame_id: int, bbox: Dict, confidence: float, class_name: str = 'deer'):
    """Add an auto-detection to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO detections (frame_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence, class_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (frame_id, bbox['x1'], bbox['y1'], bbox['x2'], bbox['y2'], confidence, class_name))
    
    conn.commit()
    conn.close()

# Annotation operations
def add_annotation(frame_id: int, bbox: Dict, annotation_type: str = 'addition', 
                   annotator: str = 'user'):
    """Add a manual annotation to the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO annotations (frame_id, bbox_x, bbox_y, bbox_width, bbox_height, 
                                annotation_type, annotator)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (frame_id, bbox['x'], bbox['y'], bbox['width'], bbox['height'], 
          annotation_type, annotator))
    
    conn.commit()
    conn.close()

def delete_annotations_for_frame(frame_id: int):
    """Delete all annotations for a specific frame."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM annotations WHERE frame_id = ?", (frame_id,))
    
    conn.commit()
    conn.close()

def get_training_statistics() -> Dict:
    """Get statistics for training readiness."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Video count
    cursor.execute("SELECT COUNT(*) as count FROM videos")
    video_count = cursor.fetchone()['count']
    
    # Frame counts
    cursor.execute("SELECT COUNT(*) as count FROM frames WHERE reviewed = 1")
    reviewed_frames = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM frames WHERE selected_for_training = 1")
    training_frames = cursor.fetchone()['count']
    
    # Annotation count
    cursor.execute("SELECT COUNT(*) as count FROM annotations")
    annotation_count = cursor.fetchone()['count']
    
    # Detection count
    cursor.execute("SELECT COUNT(*) as count FROM detections")
    detection_count = cursor.fetchone()['count']
    
    # Review breakdown
    cursor.execute("""
        SELECT review_type, COUNT(*) as count 
        FROM frames 
        WHERE review_type IS NOT NULL 
        GROUP BY review_type
    """)
    review_breakdown = {row['review_type']: row['count'] for row in cursor.fetchall()}
    
    conn.close()
    
    return {
        'video_count': video_count,
        'reviewed_frames': reviewed_frames,
        'training_frames': training_frames,
        'annotation_count': annotation_count,
        'detection_count': detection_count,
        'review_breakdown': review_breakdown,
        'ready_for_review': video_count >= 10,
        'ready_for_training': reviewed_frames >= 50 and video_count >= 10
    }

def select_diverse_frames(target_count: int = 120) -> List[int]:
    """
    Select diverse frames across all videos for training.
    Returns list of frame IDs.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all videos
    cursor.execute("SELECT id FROM videos ORDER BY created_at")
    video_ids = [row['id'] for row in cursor.fetchall()]
    
    if not video_ids:
        conn.close()
        return []
    
    frames_per_video = max(1, target_count // len(video_ids))
    selected_frame_ids = []
    
    for video_id in video_ids:
        # Get frame distribution for this video
        cursor.execute("""
            SELECT f.id, f.frame_number, f.timestamp_in_video,
                   COUNT(DISTINCT d.id) as detection_count
            FROM frames f
            LEFT JOIN detections d ON f.id = d.frame_id
            WHERE f.video_id = ?
            GROUP BY f.id
            ORDER BY f.frame_number
        """, (video_id,))
        
        all_frames = cursor.fetchall()
        
        if not all_frames:
            continue
        
        # Select frames with diversity strategy
        total_frames = len(all_frames)
        step = max(1, total_frames // frames_per_video)
        
        # Select evenly distributed frames
        for i in range(0, total_frames, step):
            if len(selected_frame_ids) >= target_count:
                break
            selected_frame_ids.append(all_frames[i]['id'])
        
        # Also include frames with detections
        frames_with_detections = [f for f in all_frames if f['detection_count'] > 0]
        for frame in frames_with_detections[:frames_per_video // 2]:
            if frame['id'] not in selected_frame_ids and len(selected_frame_ids) < target_count:
                selected_frame_ids.append(frame['id'])
    
    # Mark selected frames
    if selected_frame_ids:
        placeholders = ','.join('?' * len(selected_frame_ids))
        cursor.execute(f"""
            UPDATE frames 
            SET selected_for_training = 1 
            WHERE id IN ({placeholders})
        """, selected_frame_ids)
        conn.commit()
    
    conn.close()
    return selected_frame_ids


# Ring event logging functions
def log_ring_event(camera_id: str, event_type: str, timestamp: str, 
                   snapshot_available: bool = False, snapshot_size: int = None,
                   snapshot_path: str = None, recording_url: str = None) -> int:
    """Log a Ring camera event for diagnostics."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO ring_events (camera_id, event_type, timestamp, snapshot_available,
                                snapshot_size, snapshot_path, recording_url, processed)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    """, (camera_id, event_type, timestamp, snapshot_available, snapshot_size, snapshot_path, recording_url))
    
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return event_id


def create_ring_event(event_data: dict) -> int:
    """Create a Ring event from a dictionary of event data."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO ring_events (camera_id, event_type, timestamp, snapshot_available,
                                snapshot_size, snapshot_path, recording_url, processed,
                                deer_detected, detection_confidence, archived)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event_data.get('camera_id'),
        event_data.get('event_type'),
        event_data.get('timestamp'),
        event_data.get('snapshot_available', 0),
        event_data.get('snapshot_size'),
        event_data.get('snapshot_path'),
        event_data.get('recording_url'),
        event_data.get('processed', 0),
        event_data.get('deer_detected'),
        event_data.get('detection_confidence'),
        event_data.get('archived', 0)
    ))
    
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    logger.info(f"Created ring event {event_id} for camera {event_data.get('camera_id')}")
    return event_id


def update_ring_event_result(event_id: int, processed: bool = True, 
                             deer_detected: bool = None, confidence: float = None,
                             error_message: str = None):
    """Update Ring event with detection results."""
    conn = get_connection()
    cursor = conn.cursor()
    
    updates = ["processed = ?"]
    params = [processed]
    
    if deer_detected is not None:
        updates.append("deer_detected = ?")
        params.append(deer_detected)
    
    if confidence is not None:
        updates.append("detection_confidence = ?")
        params.append(confidence)
    
    if error_message is not None:
        updates.append("error_message = ?")
        params.append(error_message)
    
    params.append(event_id)
    
    query = f"UPDATE ring_events SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(query, params)
    
    conn.commit()
    conn.close()


def get_ring_events(hours: int = 24, camera_id: str = None) -> List[Dict]:
    """Get Ring events from the last N hours."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT * FROM ring_events 
        WHERE datetime(timestamp) >= datetime('now', '-{} hours')
    """.format(hours)
    
    params = []
    if camera_id:
        query += " AND camera_id = ?"
        params.append(camera_id)
    
    query += " ORDER BY timestamp DESC"
    
    cursor.execute(query, params)
    events = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return events


def get_ring_events_with_snapshots(limit: int = 100, with_deer: bool = None) -> List[Dict]:
    """Get Ring events that have saved snapshots (non-archived only)."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM ring_events WHERE snapshot_path IS NOT NULL AND (archived = 0 OR archived IS NULL)"
    
    if with_deer is not None:
        if with_deer:
            query += " AND deer_detected = 1"
        else:
            query += " AND (deer_detected = 0 OR deer_detected IS NULL)"
    
    query += " ORDER BY timestamp DESC LIMIT ?"
    
    cursor.execute(query, (limit,))
    events = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return events


def get_archived_ring_snapshots(limit: int = 1000) -> List[Dict]:
    """Get archived Ring snapshots."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT id as event_id, camera_id, timestamp as event_time, 
               snapshot_path, deer_detected, detection_confidence as confidence_score
        FROM ring_events 
        WHERE snapshot_path IS NOT NULL AND archived = 1
        ORDER BY timestamp DESC LIMIT ?
    """
    
    cursor.execute(query, (limit,))
    events = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return events


def archive_ring_snapshot(event_id: int) -> bool:
    """Archive a Ring snapshot."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE ring_events SET archived = 1 WHERE id = ?", (event_id,))
    success = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return success


def unarchive_ring_snapshot(event_id: int) -> bool:
    """Unarchive a Ring snapshot."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE ring_events SET archived = 0 WHERE id = ?", (event_id,))
    success = cursor.rowcount > 0
    
    conn.commit()
    conn.close()
    
    return success


def auto_archive_old_snapshots(days: int = 3) -> int:
    """Archive snapshots older than specified days. Returns count of archived snapshots."""
    from datetime import datetime, timedelta
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Calculate cutoff timestamp in local time
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    # Archive snapshots older than X days
    query = """
        UPDATE ring_events 
        SET archived = 1 
        WHERE snapshot_path IS NOT NULL 
        AND archived = 0 
        AND timestamp < ?
    """
    
    cursor.execute(query, (cutoff,))
    count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    logger.info(f"Auto-archived {count} snapshots older than {days} days (cutoff: {cutoff})")
    return count


def cleanup_old_snapshots(event_type: str, deer_detected: bool, older_than: str) -> int:
    """Delete old snapshots and their database entries based on criteria. Returns count of deleted snapshots."""
    import os
    from pathlib import Path
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Find snapshots matching criteria
    query = """
        SELECT id, snapshot_path 
        FROM ring_events 
        WHERE event_type = ? 
        AND deer_detected = ? 
        AND timestamp < ?
        AND snapshot_path IS NOT NULL
    """
    
    cursor.execute(query, (event_type, 1 if deer_detected else 0, older_than))
    snapshots = cursor.fetchall()
    
    deleted_count = 0
    for snapshot_id, snapshot_path in snapshots:
        # Delete physical file if it exists
        if snapshot_path:
            # Try both absolute and relative paths
            file_paths = [
                Path(f"/app/{snapshot_path}"),
                Path(snapshot_path)
            ]
            
            for file_path in file_paths:
                if file_path.exists():
                    try:
                        file_path.unlink()
                        logger.debug(f"Deleted snapshot file: {file_path}")
                        break
                    except Exception as e:
                        logger.warning(f"Failed to delete {file_path}: {e}")
        
        # Delete database entry
        cursor.execute("DELETE FROM ring_events WHERE id = ?", (snapshot_id,))
        deleted_count += 1
    
    conn.commit()
    conn.close()
    
    logger.info(f"Cleaned up {deleted_count} snapshots (type={event_type}, deer={deer_detected}, older_than={older_than})")
    return deleted_count


def get_ring_event_by_id(event_id: int) -> Optional[Dict]:
    """Get a specific Ring event by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM ring_events WHERE id = ?", (event_id,))
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        return dict(row)
    return None


def clear_video_annotation_flag(video_id: int):
    """Clear reviewed flags for all frames of a video (used after adding new frames)."""
    # Note: The fully_annotated status is calculated dynamically,
    # so we don't need to update anything. This function exists for
    # clarity in migration scripts but doesn't actually need to do anything.
    pass
