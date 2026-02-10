"""
FastAPI backend for Deer Deterrent System.
Provides REST API and WebSocket for real-time updates.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from pathlib import Path
import sys
import json
import asyncio
import logging
from collections import defaultdict
import tempfile
import shutil
import base64
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add parent directory to path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)
print(f"Project root: {project_root}")

# Import database module
import database as db

# Lazy imports - only load when needed
detector = None
r2_storage = None

def load_detector():
    """Lazy load detector to avoid import errors if dependencies not installed."""
    global detector
    if detector is None:
        try:
            # Try OpenVINO detector first (1.94x faster than PyTorch)
            from src.inference.detector_openvino import DeerDetectorOpenVINO
            import os
            from pathlib import Path
            
            # In Docker, main.py is at /app/main.py, so project root is /app
            project_root = Path(__file__).parent
            
            # OpenVINO model (legacy - YOLO26s v2.0 uses PyTorch via ml-detector service)
            openvino_model = project_root / "models" / "production" / "openvino" / "best_fp16.xml"
            
            if openvino_model.exists():
                detector = DeerDetectorOpenVINO(model_path=str(openvino_model), conf_threshold=0.6)
                print(f"✓ OpenVINO detector initialized: {openvino_model}")
                print(f"  Performance: ~29ms inference (1.94x faster than PyTorch)")
            else:
                # Fall back to PyTorch detector
                from src.inference.detector import DeerDetector
                
                production_model = project_root / "models" / "production" / "best.pt"
                fallback_model = project_root / "models" / "deer_detector_best.pt"
                base_model = project_root / "yolo26s.pt"
                
                if production_model.exists():
                    model_path = str(production_model)
                elif fallback_model.exists():
                    model_path = str(fallback_model)
                elif base_model.exists():
                    model_path = str(base_model)
                else:
                    model_path = "yolo26s.pt"  # Download default if needed
                    
                detector = DeerDetector(model_path=model_path, conf_threshold=0.6)
                print(f"✓ PyTorch detector initialized with model: {model_path}")
                print(f"  (Consider deploying OpenVINO model for better performance)")
        except Exception as e:
            print(f"⚠ Detector initialization failed: {e}")
            print("  Running in demo mode - detection features disabled")
    return detector

def load_r2_storage():
    """Lazy load R2 storage client."""
    global r2_storage
    if r2_storage is None:
        try:
            from src.services.r2_sync import R2Storage
            account_id = os.getenv('R2_ACCOUNT_ID')
            access_key = os.getenv('R2_ACCESS_KEY_ID')
            secret_key = os.getenv('R2_SECRET_ACCESS_KEY')
            bucket_name = os.getenv('R2_BUCKET_NAME', 'deer-deterrent')
            
            if account_id and access_key and secret_key:
                r2_storage = R2Storage(account_id, access_key, secret_key, bucket_name)
                logger.info(f"R2 storage client initialized: {bucket_name}")
            else:
                logger.warning("R2 credentials not configured - backup disabled")
        except Exception as e:
            logger.error(f"Failed to initialize R2 storage: {e}")
    return r2_storage

try:
    import cv2
    import numpy as np
    import base64
    CV2_AVAILABLE = True
except ImportError:
    print("⚠ OpenCV/NumPy not available - image processing disabled")
    CV2_AVAILABLE = False

app = FastAPI(
    title="Deer Deterrent API",
    description="Real-time deer detection and irrigation control",
    version="1.0.0"
)

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database and load detector."""
    print("Initializing database...")
    db.init_database()
    print("Database ready!")

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://deer-deterrent-rnp.web.app",
        "https://deer.rndpig.com",
        "https://deer-deterrent.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Debug endpoint
@app.get("/api/debug/env")
async def debug_env():
    """Debug endpoint to check environment variables"""
    import os
    from pathlib import Path
    return {
        "GOOGLE_DRIVE_CREDENTIALS_PATH": os.getenv('GOOGLE_DRIVE_CREDENTIALS_PATH'),
        "GOOGLE_DRIVE_TRAINING_FOLDER_ID": os.getenv('GOOGLE_DRIVE_TRAINING_FOLDER_ID'),
        "credentials_file_exists": Path(os.getenv('GOOGLE_DRIVE_CREDENTIALS_PATH', 'configs/google-credentials.json')).exists(),
        "cwd": os.getcwd(),
        "all_google_env": {k: v for k, v in os.environ.items() if 'GOOGLE' in k}
    }

# Initialize detector
detector = None
detection_history = []  # Legacy - will be phased out
detection_reviews = {}  # Store manual reviews for training
missed_detections = []  # Store user-reported missed deer
active_websockets = []

# Models
class DetectionEvent(BaseModel):
    timestamp: str
    camera_name: str
    zone_name: str
    deer_count: int
    max_confidence: float
    image_path: str
    irrigation_activated: bool
    reviewed: bool = False
    review_type: Optional[str] = None
    id: Optional[str] = None
    detections: List[Dict] = []
    manual_annotations: List[Dict] = []
    frame_number: Optional[int] = None

    class Config:
        extra = "allow"  # Allow extra fields from detection_history

class DetectionReview(BaseModel):
    detection_id: str
    review_type: str  # 'correct', 'false_positive', 'missed_deer', 'incorrect_count'
    corrected_deer_count: int = None
    notes: str = None
    reviewed_at: str = None
    reviewer: str = "admin"

class MissedDetection(BaseModel):
    timestamp: str
    camera_name: str
    deer_count: int
    notes: str = None
    reporter: str = "user"

class SystemSettings(BaseModel):
    confidence_threshold: float = 0.55
    season_start: str = "04-01"
    season_end: str = "10-31"
    active_hours_enabled: bool = True
    active_hours_start: int = 20
    active_hours_end: int = 6
    irrigation_duration: int = 30
    zone_cooldown: int = 300
    dry_run: bool = True
    snapshot_archive_days: int = 3
    snapshot_frequency: int = 60  # Ring camera snapshot capture frequency in seconds (15, 30, 60, 180)
    enabled_cameras: List[str] = ["10cea9e4511f"]  # Default: Side camera only

class ZoneConfig(BaseModel):
    name: str
    camera_id: str
    detection_area: Dict[str, float]
    irrigation_zones: List[int]

# Ring camera device ID mapping (comment field from video metadata)
# Device ID format: gml.{camera_id}.{session_id}
# We only use the camera_id part (middle section between periods)
RING_DEVICE_ID_MAP = {
    "27c3cea0rmpl": "Driveway",  # Main camera ID for Driveway
    "768534ffrmpl": "Side",      # Main camera ID for Side
    "0268c865rmpl": "Side",      # Alternate device ID for Side camera
}

# Ring-MQTT camera ID mapping (from MQTT topics)
RING_CAMERA_ID_MAP = {
    "587a624d3fae": "Driveway",
    "4439c4de7a79": "Front Door",
    "f045dae9383a": "Back",
    "10cea9e4511f": "Side"
}

# Manual overrides for specific videos where device ID mapping is wrong
# Format: {filename: "CameraName"}
VIDEO_CAMERA_OVERRIDES = {
    "RingVideo_20251205_075319.mp4": "Side",  # Actually shows green/side area
    "RingVideo_20251205_075329.mp4": "Side",  # Actually shows green/side area
    "RingVideo_20251115_064703.MP4": "Driveway",  # Device ID says Side but shows driveway
    "RingVideo_20251120_064019.mp4": "Side",  # Device ID says Driveway but shows side
}

# In-memory storage (will move to SQLite later)
settings = SystemSettings()
zones = []
stats = {
    "total_detections": 0,
    "total_deer": 0,
    "irrigation_activated": 0,
    "last_detection": None
}


async def auto_archive_task():
    """Background task to periodically archive old snapshots."""
    while True:
        try:
            # Wait 1 hour before first run, then every hour
            await asyncio.sleep(3600)
            
            # Archive snapshots older than configured days
            count = db.auto_archive_old_snapshots(days=settings.snapshot_archive_days)
            
            if count > 0:
                logger.info(f"Auto-archived {count} snapshots older than {settings.snapshot_archive_days} days")
        except Exception as e:
            logger.error(f"Error in auto-archive task: {e}")


@app.on_event("startup")
async def startup_event():
    """Initialize detector on startup."""
    # Detector loaded lazily when first needed
    print("✓ Backend started - detector will load on first use")
    # Start background task for auto-archiving snapshots
    asyncio.create_task(auto_archive_task())
    print("✓ Auto-archive task started")


@app.get("/")
async def root():
    """Health check."""
    return {
        "status": "ok",
        "name": "Deer Deterrent API",
        "version": "1.0.0",
        "detector_loaded": detector is not None
    }


@app.get("/health")
async def health():
    """Simple health check for Docker."""
    return {"status": "healthy"}


@app.get("/api/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "detector": "ready" if detector else "not loaded",
        "websocket_clients": len(active_websockets),
        "uptime": "running"
    }


@app.get("/api/stats")
async def get_stats():
    """Get system statistics."""
    return {
        **stats,
        "detection_history_count": len(detection_history),
        "current_season": is_in_season(),
    }


@app.get("/api/ring-events")
async def get_ring_events(hours: int = 24, camera_id: str = None):
    """Get Ring MQTT events from the last N hours for diagnostics."""
    events = db.get_ring_events(hours=hours, camera_id=camera_id)
    return {
        "events": events,
        "total_count": len(events),
        "hours": hours,
        "camera_id": camera_id
    }


@app.post("/api/ring-events")
async def create_ring_event(event: dict):
    """Log a Ring MQTT event for diagnostics."""
    event_id = db.log_ring_event(
        camera_id=event.get("camera_id"),
        event_type=event.get("event_type"),
        timestamp=event.get("timestamp"),
        snapshot_available=event.get("snapshot_available", False),
        snapshot_size=event.get("snapshot_size"),
        snapshot_path=event.get("snapshot_path"),
        recording_url=event.get("recording_url")
    )
    return {"status": "success", "event_id": event_id}


@app.patch("/api/ring-events/{event_id}")
async def update_ring_event(event_id: int, update: dict):
    """Update Ring event with detection results."""
    deer_detected = update.get("deer_detected")
    
    # Only re-detect for USER-initiated "yes-deer" clicks (which send just {deer_detected: 1})
    # Skip re-detection for coordinator updates (which include "confidence" and "detection_bboxes")
    is_user_feedback = "confidence" not in update and "detection_bboxes" not in update
    
    if (deer_detected == 1 or deer_detected == True) and is_user_feedback:
        detector_obj = load_detector()
        if detector_obj:
            try:
                # Get event and snapshot
                event = db.get_ring_event_by_id(event_id)
                if event and event.get('snapshot_path'):
                    snapshot_path = Path(event['snapshot_path'])
                    if not snapshot_path.is_absolute():
                        snapshot_path = Path("/app") / snapshot_path
                    
                    if snapshot_path.exists():
                        import cv2
                        
                        # Load image
                        img = cv2.imread(str(snapshot_path))
                        if img is not None:
                            # Run detection with lower threshold to catch the deer user saw
                            original_threshold = detector_obj.conf_threshold
                            detector_obj.conf_threshold = 0.15  # Lower threshold for user-confirmed deer
                            
                            detections_list, _ = detector_obj.detect(img, return_annotated=False)
                            
                            # Restore original threshold
                            detector_obj.conf_threshold = original_threshold
                            
                            # Format results
                            detections = []
                            max_confidence = 0.0
                            
                            for det in detections_list:
                                confidence = det['confidence']
                                detections.append({
                                    "confidence": confidence,
                                    "bbox": det['bbox']
                                })
                                if confidence > max_confidence:
                                    max_confidence = confidence
                            
                            # Update with detection results
                            if len(detections) > 0:
                                update["confidence"] = max_confidence
                                update["detection_bboxes"] = detections
                                # Include model version
                                model_name = type(detector_obj).__name__
                                if 'OpenVINO' in model_name:
                                    update["model_version"] = "YOLO26s v2.0 OpenVINO"
                                else:
                                    update["model_version"] = "YOLO26s v2.0 PyTorch"
                                logger.info(f"Snapshot {event_id} re-detected with {len(detections)} boxes, confidence: {max_confidence:.2f}, model: {update['model_version']}")
                            else:
                                # User says deer but detector didn't find any - still mark as deer with 0 confidence
                                update["confidence"] = 0.0
                                update["detection_bboxes"] = []
                                model_name = type(detector_obj).__name__
                                if 'OpenVINO' in model_name:
                                    update["model_version"] = "YOLO26s v2.0 OpenVINO"
                                else:
                                    update["model_version"] = "YOLO26s v2.0 PyTorch"
                                logger.warning(f"Snapshot {event_id} marked as deer by user but detector found none")
            except Exception as e:
                logger.error(f"Error running detection for user feedback on snapshot {event_id}: {e}")
                # Continue with update even if detection fails
    
    db.update_ring_event_result(
        event_id=event_id,
        processed=update.get("processed", True),
        deer_detected=update.get("deer_detected"),
        confidence=update.get("confidence"),
        error_message=update.get("error_message"),
        detection_bboxes=update.get("detection_bboxes"),
        model_version=update.get("model_version")
    )
    return {"status": "success"}


@app.get("/api/snapshots")
async def get_ring_snapshots(limit: int = 100, with_deer: bool = None):
    """Get Ring snapshots with metadata."""
    events = db.get_ring_events_with_snapshots(limit=limit, with_deer=with_deer)
    
    # Add snapshot file info
    for event in events:
        snapshot_path = event.get('snapshot_path')
        if snapshot_path:
            snapshot_file = Path(snapshot_path)
            if not snapshot_file.is_absolute():
                snapshot_file = Path("/app") / snapshot_path
            
            event['snapshot_exists'] = snapshot_file.exists()
            if event['snapshot_exists']:
                event['snapshot_size_bytes'] = snapshot_file.stat().st_size
    
    return {
        "snapshots": events,
        "total_count": len(events),
        "limit": limit,
        "filter": "with_deer" if with_deer else "all"
    }


@app.get("/api/snapshots/{event_id}/image")
async def get_snapshot_image(event_id: int):
    """Serve snapshot image file."""
    event = db.get_ring_event_by_id(event_id)
    if not event or not event.get('snapshot_path'):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    # Handle both absolute and relative paths
    snapshot_path = Path(event['snapshot_path'])
    if not snapshot_path.is_absolute():
        # Relative path - resolve from /app
        snapshot_path = Path("/app") / snapshot_path
    
    if not snapshot_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot file not found")
    
    return FileResponse(
        path=str(snapshot_path),
        media_type="image/jpeg",
        filename=snapshot_path.name
    )


@app.post("/api/snapshots/{event_id}/rerun-detection")
async def rerun_snapshot_detection(event_id: int, threshold: float = 0.15):
    """Re-run ML detection on a saved snapshot."""
    detector_obj = load_detector()
    if not detector_obj:
        raise HTTPException(status_code=503, detail="Detector not initialized")
    
    # Get event and snapshot
    event = db.get_ring_event_by_id(event_id)
    if not event or not event.get('snapshot_path'):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    snapshot_path = Path(event['snapshot_path'])
    if not snapshot_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot file not found")
    
    try:
        import cv2
        import numpy as np
        
        # Load image
        img = cv2.imread(str(snapshot_path))
        if img is None:
            raise HTTPException(status_code=400, detail="Failed to load image")
        
        # Run detection with specified threshold
        # Temporarily adjust detector threshold
        original_threshold = detector_obj.conf_threshold
        detector_obj.conf_threshold = threshold
        
        detections_list, _ = detector_obj.detect(img, return_annotated=False)
        
        # Restore original threshold
        detector_obj.conf_threshold = original_threshold
        
        # Format results
        detections = []
        max_confidence = 0.0
        
        for det in detections_list:
            confidence = det['confidence']
            detections.append({
                "confidence": confidence,
                "bbox": det['bbox']
            })
            if confidence > max_confidence:
                max_confidence = confidence
        
        deer_detected = len(detections) > 0
        
        # Optionally update database
        db.update_ring_event_result(
            event_id=event_id,
            processed=True,
            deer_detected=deer_detected,
            confidence=max_confidence if deer_detected else 0.0,
            detection_bboxes=detections if deer_detected else []
        )
        
        return {
            "event_id": event_id,
            "deer_detected": deer_detected,
            "detection_count": len(detections),
            "max_confidence": max_confidence,
            "threshold": threshold,
            "detections": detections,
            "image_size": {
                "width": img.shape[1],
                "height": img.shape[0]
            }
        }
        
    except Exception as e:
        logger.error(f"Detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/snapshots/archived")
async def get_archived_snapshots(limit: int = 1000):
    """Get archived Ring snapshots."""
    events = db.get_archived_ring_snapshots(limit=limit)
    
    return {
        "snapshots": events,
        "total_count": len(events),
        "limit": limit
    }


@app.post("/api/snapshots/{event_id}/archive")
async def archive_snapshot(event_id: int):
    """Archive a Ring snapshot."""
    success = db.archive_ring_snapshot(event_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    return {"success": True, "event_id": event_id, "archived": True}


@app.post("/api/snapshots/{event_id}/unarchive")
async def unarchive_snapshot(event_id: int):
    """Unarchive a Ring snapshot."""
    success = db.unarchive_ring_snapshot(event_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    return {"success": True, "event_id": event_id, "archived": False}


@app.post("/api/ring-snapshots/auto-archive")
async def auto_archive_snapshots(days: int = 3):
    """Auto-archive snapshots older than specified days."""
    count = db.auto_archive_old_snapshots(days=days)
    
    return {
        "success": True,
        "archived_count": count,
        "days_threshold": days
    }


@app.post("/api/cleanup-old-snapshots")
async def cleanup_old_snapshots(request: dict):
    """Delete old snapshots based on criteria (event_type, deer_detected, age)."""
    event_type = request.get("event_type")
    deer_detected = request.get("deer_detected")
    older_than = request.get("older_than")
    
    if not all([event_type, older_than is not None, deer_detected is not None]):
        raise HTTPException(status_code=400, detail="Missing required parameters")
    
    deleted_count = db.cleanup_old_snapshots(
        event_type=event_type,
        deer_detected=deer_detected,
        older_than=older_than
    )
    
    return {
        "success": True,
        "deleted": deleted_count,
        "criteria": {
            "event_type": event_type,
            "deer_detected": deer_detected,
            "older_than": older_than
        }
    }


@app.get("/api/training-archive/stats")
async def get_training_archive_stats():
    """Get statistics about the training data archive (negatives collected per camera)."""
    from pathlib import Path
    
    archive_base = Path("/app/data/training_archive/negatives")
    stats = {"cameras": {}, "total_images": 0, "total_size_mb": 0.0}
    
    if archive_base.exists():
        for camera_dir in sorted(archive_base.iterdir()):
            if camera_dir.is_dir():
                files = list(camera_dir.glob("*.jpg"))
                size_bytes = sum(f.stat().st_size for f in files)
                stats["cameras"][camera_dir.name] = {
                    "count": len(files),
                    "size_mb": round(size_bytes / (1024 * 1024), 2)
                }
                stats["total_images"] += len(files)
                stats["total_size_mb"] += size_bytes / (1024 * 1024)
    
    stats["total_size_mb"] = round(stats["total_size_mb"], 2)
    return stats


@app.delete("/api/ring-snapshots/{event_id}")
async def delete_snapshot(event_id: int):
    """Delete a specific snapshot by event ID."""
    import os
    
    # Get the event to find the snapshot path
    event = db.get_ring_event_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    # Delete the physical file if it exists
    snapshot_path = event.get('snapshot_path')
    if snapshot_path:
        # Try both possible paths
        for base_path in ['/app/data/snapshots/', '/app/snapshots/']:
            full_path = os.path.join(base_path, os.path.basename(snapshot_path))
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    logger.info(f"Deleted snapshot file: {full_path}")
                except Exception as e:
                    logger.error(f"Failed to delete file {full_path}: {e}")
    
    # Delete from database
    db.delete_ring_event(event_id)
    logger.info(f"Deleted snapshot event {event_id} from database")
    
    return {"success": True, "deleted_event_id": event_id}


@app.post("/api/test-detection")
async def test_detection(
    image: UploadFile = File(...), 
    threshold: float = Form(0.6),
    save_to_database: bool = Form(False),
    camera_id: str = Form(None),
    captured_at: str = Form(None)
):
    """Test deer detection on an uploaded image and optionally save to database."""
    detector_obj = load_detector()
    if not detector_obj:
        raise HTTPException(status_code=503, detail="Detector not initialized")
    
    # Log parameters for debugging
    logger.info(f"test_detection called with threshold={threshold}, save_to_database={save_to_database}")
    
    # Validate file type
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        import cv2
        import numpy as np
        from datetime import datetime
        
        # Read image bytes
        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Failed to decode image")
        
        # Run detection with specified threshold
        original_threshold = detector_obj.conf_threshold
        detector_obj.conf_threshold = threshold
        
        detections_list, _ = detector_obj.detect(img, return_annotated=False)
        
        # Restore original threshold
        detector_obj.conf_threshold = original_threshold
        
        # Format results
        detections = []
        max_confidence = 0.0
        
        for det in detections_list:
            confidence = det['confidence']
            detections.append({
                "confidence": confidence,
                "bbox": det['bbox'],
                "class_name": det.get('class_name', 'deer')
            })
            if confidence > max_confidence:
                max_confidence = confidence
        
        deer_detected = len(detections) > 0
        saved_event_id = None
        
        # Save to database if requested
        if save_to_database:
            # Save image to data/snapshots directory (writable location)
            snapshot_dir = Path("/app/data/snapshots")
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            
            # Use provided timestamp or current time
            if captured_at:
                try:
                    from dateutil import parser
                    timestamp = parser.parse(captured_at)
                except:
                    logger.warning(f"Failed to parse captured_at: {captured_at}, using current time")
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now()
            
            filename = f"manual_upload_{timestamp.strftime('%Y%m%d_%H%M%S')}.jpg"
            snapshot_path = snapshot_dir / filename
            
            # Save the image
            cv2.imwrite(str(snapshot_path), img)
            
            # Use provided camera_id or default to 'manual_upload'
            final_camera_id = camera_id if camera_id else 'manual_upload'
            
            # Create database entry
            event_data = {
                'camera_id': final_camera_id,
                'event_type': 'manual_upload',
                'timestamp': timestamp.isoformat(),
                'snapshot_available': 1,
                'snapshot_size': len(contents),
                'snapshot_path': f"data/snapshots/{filename}",
                'processed': 1,
                'deer_detected': 1 if deer_detected else 0,
                'detection_confidence': max_confidence,
                'archived': 0
            }
            
            saved_event_id = db.create_ring_event(event_data)
            logger.info(f"Saved manual upload to database as event {saved_event_id} (camera: {final_camera_id}, time: {timestamp.isoformat()})")
        
        return {
            "deer_detected": deer_detected,
            "max_confidence": max_confidence,
            "detections": detections,
            "detection_count": len(detections),
            "threshold_used": threshold,
            "saved_event_id": saved_event_id
        }
        
    except Exception as e:
        logger.error(f"Error testing detection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/coordinator/stats")
async def get_coordinator_stats():
    """Proxy coordinator stats to avoid CORS issues."""
    import requests
    try:
        # Use Docker service name instead of IP (coordinator is on same network)
        response = requests.get("http://deer-coordinator:5000/stats", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Failed to fetch coordinator stats: {e}")
        raise HTTPException(status_code=503, detail="Coordinator unavailable")


@app.get("/api/coordinator/logs")
async def get_coordinator_logs(lines: int = 100):
    """Get recent coordinator logs."""
    import docker
    try:
        client = docker.from_env()
        container = client.containers.get("deer-coordinator")
        logs = container.logs(tail=lines, timestamps=True).decode('utf-8')
        return {
            "logs": logs,
            "lines": lines
        }
    except Exception as e:
        logger.error(f"Failed to fetch coordinator logs: {e}")
        raise HTTPException(status_code=503, detail=f"Failed to fetch logs: {str(e)}")


@app.get("/api/detections", response_model=List[DetectionEvent])
async def get_detections(limit: int = 50, offset: int = 0):
    """Get detection history (excludes manual video uploads)."""
    # Ensure all records have max_confidence field (migration for old records)
    for detection in detection_history:
        if 'max_confidence' not in detection:
            detection['max_confidence'] = detection.get('confidence', 0.0)
    
    # Filter out manual uploads
    filtered = [d for d in detection_history if d.get("camera_name") != "Manual Upload"]
    return filtered[offset:offset + limit]


@app.get("/api/detections/recent")
async def get_recent_detections(hours: int = 24):
    """Get detections from last N hours (excludes manual video uploads)."""
    cutoff = datetime.now() - timedelta(hours=hours)
    recent = [
        d for d in detection_history
        if datetime.fromisoformat(d["timestamp"]) > cutoff
        and d.get("camera_name") != "Manual Upload"  # Exclude manual uploads
    ]
    return recent


@app.post("/api/detections")
async def create_detection(event_data: dict):
    """Log a detection event from the coordinator."""
    # Only log if deer were actually detected
    if not event_data.get('deer_detected', False):
        logger.info(f"Skipping non-deer detection from camera {event_data.get('camera_id')}")
        return {"status": "skipped", "reason": "no deer detected"}
    
    # Add unique ID if not present
    if 'id' not in event_data:
        event_data['id'] = f"{event_data.get('timestamp', '')}_{event_data.get('camera_id', '')}"
    
    # Map camera_id to camera_name using Ring-MQTT camera ID map
    camera_id = event_data.get('camera_id', '')
    if camera_id in RING_CAMERA_ID_MAP:
        event_data['camera_name'] = RING_CAMERA_ID_MAP[camera_id]
    else:
        # Fallback: use camera_id if not in map
        event_data['camera_name'] = camera_id
        logger.warning(f"Unknown camera ID '{camera_id}' - add to RING_CAMERA_ID_MAP")
    
    # Ensure required fields with defaults
    event_data.setdefault('zone_name', '')  # Empty zone name - not used on frontend
    event_data.setdefault('deer_count', len([d for d in event_data.get('detections', []) if d.get('class', '').lower() == 'deer']))
    event_data.setdefault('max_confidence', event_data.get('confidence', 0.0))
    event_data.setdefault('image_path', event_data.get('snapshot_path', ''))
    event_data.setdefault('irrigation_activated', False)
    event_data.setdefault('reviewed', False)
    
    # Add to detection history
    detection_history.append(event_data)
    
    # Update stats
    stats['total_detections'] = len(detection_history)
    if event_data.get('deer_detected'):
        stats['total_deer'] = stats.get('total_deer', 0) + event_data.get('deer_count', 0)
    if event_data.get('irrigation_activated'):
        stats['irrigation_activated'] = stats.get('irrigation_activated', 0) + 1
    stats['last_detection'] = event_data.get('timestamp')
    
    # Broadcast via WebSocket
    await broadcast_message({
        "type": "detection",
        "data": event_data
    })
    
    logger.info(f"Logged deer detection: camera={event_data.get('camera_name')}, confidence={event_data.get('max_confidence'):.2f}")
    
    return {"status": "success", "detection_id": event_data['id']}


@app.get("/api/settings", response_model=SystemSettings)
async def get_settings():
    """Get current system settings."""
    return settings


@app.put("/api/settings")
async def update_settings(new_settings: SystemSettings):
    """Update system settings."""
    global settings, detector
    settings = new_settings
    
    # Update detector confidence threshold
    if detector:
        detector.conf_threshold = settings.confidence_threshold
    
    # Broadcast update to WebSocket clients
    await broadcast_message({
        "type": "settings_updated",
        "settings": settings.dict()
    })
    
    return {"status": "updated", "settings": settings}


@app.get("/api/zones", response_model=List[ZoneConfig])
async def get_zones():
    """Get zone configurations."""
    return zones


@app.get("/api/rainbird/zones")
async def get_rainbird_zones():
    """
    Get available Rainbird irrigation zones with their names.
    
    Returns:
        List of zones with number and name
    """
    # ESP-Me local controller doesn't expose zone names via API
    # Zone names from user's Rainbird app configuration
    
    default_zones = [
        {"number": 1, "name": "Driveway North"},
        {"number": 2, "name": "Garage North"},
        {"number": 3, "name": "Patio Lawn"},
        {"number": 4, "name": "Patio N Bed"},
        {"number": 5, "name": "Woods North"},
        {"number": 6, "name": "Woods South"},
        {"number": 7, "name": "House South 1"},
        {"number": 8, "name": "Front Beds"},
        {"number": 9, "name": "Front Sidewalk"},
        {"number": 10, "name": "Driveway South"},
        {"number": 11, "name": "Road South"},
        {"number": 12, "name": "Patio S Bed"},
        {"number": 13, "name": "House South 2"},
        {"number": 14, "name": "Garage South"}
    ]
    
    return {
        "status": "success",
        "zones": default_zones
    }


@app.get("/api/ring/cameras")
async def get_ring_cameras():
    """
    Get available Ring cameras.
    
    Returns:
        List of Ring cameras with name, id, type
    """
    try:
        from src.integrations.ring_camera import RingCameraClient
        
        client = RingCameraClient()
        cameras = client.get_all_cameras()
        
        return {
            "status": "success",
            "cameras": cameras
        }
            
    except Exception as e:
        print(f"Error fetching Ring cameras: {e}")
        # Return fallback camera list
        return {
            "status": "error",
            "message": str(e),
            "cameras": [
                {"name": "Driveway", "id": "driveway", "type": "camera"},
                {"name": "Side", "id": "side", "type": "camera"},
                {"name": "Front", "id": "front", "type": "camera"},
                {"name": "Backyard", "id": "backyard", "type": "camera"}
            ]
        }


@app.put("/api/zones")
async def update_zones(new_zones: List[ZoneConfig]):
    """Update zone configurations."""
    global zones
    zones = new_zones
    return {"status": "updated", "count": len(zones)}


@app.post("/api/detect")
async def run_detection(image_file: str):
    """
    Run detection on an uploaded image.
    
    Args:
        image_file: Base64 encoded image
    """
    if not CV2_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCV not available - install opencv-python")
    
    det = load_detector()
    if not det:
        raise HTTPException(status_code=503, detail="Detector not initialized")
    
    try:
        # Decode base64 image
        image_data = base64.b64decode(image_file.split(',')[1] if ',' in image_file else image_file)
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Run detection
        detections, annotated = det.detect(image, return_annotated=True)
        
        # Encode annotated image
        _, buffer = cv2.imencode('.jpg', annotated)
        annotated_b64 = base64.b64encode(buffer).decode('utf-8')
        
        return {
            "detections": detections,
            "annotated_image": f"data:image/jpeg;base64,{annotated_b64}",
            "deer_count": len(detections)
        }
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/detect/video")
async def run_video_detection(video: UploadFile = File(...)):
    """
    Run detection on an uploaded video file.
    Processes frames and returns detections with diagnostic info.
    
    Args:
        video: Uploaded video file (mp4, mov, avi, etc.)
    
    Returns:
        Detection results including:
        - Total frames processed
        - Frames with deer detected
        - Highest confidence detection
        - All detection details
        - Annotated images for frames with detections
    """
    if not CV2_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCV not available - install opencv-python")
    
    det = load_detector()
    if not det:
        raise HTTPException(status_code=503, detail="Detector not initialized")
    
    # Create temp directory for processing
    temp_dir = Path("temp/video_uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save uploaded video to temp file
        video_path = temp_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{video.filename}"
        with video_path.open("wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        
        import cv2
        import numpy as np
        
        # Open video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Could not open video file")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Process every Nth frame (sample rate - process ~2 frames per second)
        sample_rate = max(1, int(fps / 2))
        
        results = {
            "filename": video.filename,
            "fps": fps,
            "total_frames": total_frames,
            "frames_processed": 0,
            "frames_with_detections": 0,
            "total_deer_detected": 0,
            "max_confidence": 0.0,
            "detections": [],
            "diagnostic_info": {
                "sample_rate": sample_rate,
                "frames_sampled": 0
            }
        }
        
        frame_num = 0
        detections_by_frame = []
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Only process sampled frames
            if frame_num % sample_rate == 0:
                results["frames_processed"] += 1
                results["diagnostic_info"]["frames_sampled"] += 1
                
                # Run detection
                detections, annotated = det.detect(frame, return_annotated=True)
                
                if detections:
                    results["frames_with_detections"] += 1
                    results["total_deer_detected"] += len(detections)
                    
                    # Save annotated frame
                    frame_filename = f"frame_{frame_num:06d}.jpg"
                    frame_path = temp_dir / frame_filename
                    cv2.imwrite(str(frame_path), annotated)
                    
                    # Encode frame for response
                    _, buffer = cv2.imencode('.jpg', annotated)
                    annotated_b64 = base64.b64encode(buffer).decode('utf-8')
                    
                    # Track max confidence
                    max_conf = max([d['confidence'] for d in detections])
                    if max_conf > results["max_confidence"]:
                        results["max_confidence"] = max_conf
                    
                    detections_by_frame.append({
                        "frame_number": frame_num,
                        "timestamp_seconds": frame_num / fps,
                        "deer_count": len(detections),
                        "detections": detections,
                        "annotated_image": f"data:image/jpeg;base64,{annotated_b64}",
                        "image_path": f"/api/video-frames/{frame_filename}"
                    })
            
            frame_num += 1
        
        cap.release()
        
        # Add detection details to results
        results["detections"] = detections_by_frame
        
        # Save results to database if detections found
        if results["frames_with_detections"] > 0:
            detection_entry = {
                "timestamp": datetime.now().isoformat(),
                "camera_name": "Manual Upload",
                "zone_name": "Video Analysis",
                "deer_count": results["total_deer_detected"],
                "max_confidence": results["max_confidence"],
                "irrigation_activated": False,
                "image_path": f"/api/video-frames/{detections_by_frame[0]['frame_number']:06d}.jpg" if detections_by_frame else None,
                "video_analysis": True,
                "video_filename": video.filename,
                "frames_analyzed": results["frames_processed"]
            }
            detection_history.append(detection_entry)
        
        # Clean up video file
        video_path.unlink()
        
        return results
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")
    finally:
        await video.close()


@app.get("/api/video-frames/{frame_name}")
async def get_video_frame(frame_name: str):
    """Serve extracted video frames with detections."""
    frame_path = Path("temp/video_uploads") / frame_name
    if not frame_path.exists():
        raise HTTPException(status_code=404, detail="Frame not found")
    return FileResponse(frame_path)


@app.post("/api/videos/upload")
async def upload_video_for_training(video: UploadFile = File(...), sample_rate: int = 15):
    """
    Upload video for training data extraction.
    Extracts frames at specified sampling rate, runs detection, and saves for review/annotation.
    
    Args:
        video: Uploaded video file
        sample_rate: Extract every Nth frame (default: 15, ~2 frames/sec at 30fps)
    
    This endpoint:
    - Extracts every Nth frame based on sample_rate
    - Runs detection on sampled frames
    - Saves video archive
    - Creates detection records for sampled frames
    - Adds frames to review queue
    
    Returns:
        frames_extracted: Total frames extracted
        detections_found: Frames with automatic detections
        video_saved: Path to archived video
        sample_rate: Sampling rate used
    """
    if not CV2_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCV not available")
    
    det = load_detector()
    if not det:
        raise HTTPException(status_code=503, detail="Detector not initialized")
    
    # Validate sample_rate
    if sample_rate < 1:
        sample_rate = 1
    elif sample_rate > 120:
        sample_rate = 120
    
    # Create directories
    video_archive_dir = Path("data/video_archive")
    frames_dir = Path("data/frames")
    video_archive_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Save video to archive
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        video_filename = f"{timestamp}_{video.filename}"
        video_save_path = video_archive_dir / video_filename
        
        with video_save_path.open("wb") as buffer:
            shutil.copyfileobj(video.file, buffer)
        
        import cv2
        import numpy as np
        import re
        
        # Try to extract recording timestamp and camera name from filename first (Ring videos: RingVideo_YYYYMMDD_HHMMSS.mp4)
        recording_timestamp = None
        detected_camera = None
        try:
            # Match pattern: RingVideo_YYYYMMDD_HHMMSS
            match = re.search(r'RingVideo_(\d{8})_(\d{6})', video.filename)
            if match:
                date_str = match.group(1)  # YYYYMMDD
                time_str = match.group(2)  # HHMMSS
                # Parse into datetime: YYYYMMDD_HHMMSS -> YYYY-MM-DD HH:MM:SS
                year = date_str[0:4]
                month = date_str[4:6]
                day = date_str[6:8]
                hour = time_str[0:2]
                minute = time_str[2:4]
                second = time_str[4:6]
                recording_timestamp = f"{year}-{month}-{day} {hour}:{minute}:{second}"
                logger.info(f"Extracted recording timestamp from Ring filename: {recording_timestamp}")
        except Exception as e:
            logger.warning(f"Could not parse Ring filename for timestamp: {e}")
        
        # Try to extract timestamp from video overlay using OCR
        ocr_timestamp = None
        try:
            import pytesseract
            from PIL import Image
            
            # Open video and extract first frame
            cap_temp = cv2.VideoCapture(str(video_save_path))
            if cap_temp.isOpened():
                ret, first_frame = cap_temp.read()
                cap_temp.release()
                
                if ret:
                    # Ring cameras put timestamp in bottom-right corner
                    # Extract bottom-right region (adjust coordinates based on your video resolution)
                    h, w = first_frame.shape[:2]
                    timestamp_region = first_frame[int(h*0.92):h, int(w*0.65):w]  # Bottom-right ~8% height, ~35% width
                    
                    # Preprocess for better OCR: convert to grayscale, increase contrast
                    gray = cv2.cvtColor(timestamp_region, cv2.COLOR_BGR2GRAY)
                    # Increase contrast
                    gray = cv2.convertScaleAbs(gray, alpha=2.0, beta=0)
                    # Apply threshold to get white text on black background
                    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
                    
                    # Convert to PIL Image for tesseract
                    pil_img = Image.fromarray(thresh)
                    
                    # Extract text using OCR
                    ocr_text = pytesseract.image_to_string(pil_img, config='--psm 6')
                    logger.info(f"OCR extracted text from video overlay: {ocr_text.strip()}")
                    
                    # Parse timestamp from OCR text
                    # Ring format can be: "MM/DD/YYYY HH:MM:SS AM/PM TIMEZONE" or "MM/DD/YYYY HH:MM:SS TIMEZONE"
                    # Example: "11/23/2025 01:22:36 AM CST" or "11/23/2025 01:22:36 CST"
                    import re
                    # Try pattern with AM/PM first
                    timestamp_pattern = r'(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}:\d{2})\s+(AM|PM)'
                    match = re.search(timestamp_pattern, ocr_text)
                    if match:
                        date_part = match.group(1)  # MM/DD/YYYY
                        time_part = match.group(2)  # HH:MM:SS
                        am_pm = match.group(3)       # AM or PM
                        
                        # Parse and convert to 24-hour format
                        dt_str = f"{date_part} {time_part} {am_pm}"
                        dt = datetime.strptime(dt_str, "%m/%d/%Y %I:%M:%S %p")
                        ocr_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                        logger.info(f"Successfully extracted timestamp from video overlay: {ocr_timestamp}")
                        recording_timestamp = ocr_timestamp  # Override filename timestamp
                    else:
                        # Try pattern without AM/PM (already in 24-hour format)
                        timestamp_pattern = r'(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}:\d{2})'
                        match = re.search(timestamp_pattern, ocr_text)
                        if match:
                            date_part = match.group(1)  # MM/DD/YYYY
                            time_part = match.group(2)  # HH:MM:SS
                            
                            # Parse as 24-hour format
                            dt_str = f"{date_part} {time_part}"
                            dt = datetime.strptime(dt_str, "%m/%d/%Y %H:%M:%S")
                            ocr_timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                            logger.info(f"Successfully extracted timestamp from video overlay: {ocr_timestamp}")
                            recording_timestamp = ocr_timestamp  # Override filename timestamp
        except Exception as e:
            logger.warning(f"Could not extract timestamp from video overlay using OCR: {e}")
        
        # Try to extract metadata from video file (timestamp and camera info)
        video_metadata = {}
        try:
            import subprocess
            result = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', str(video_save_path)],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                import json
                metadata = json.loads(result.stdout)
                format_tags = metadata.get('format', {}).get('tags', {})
                video_metadata = format_tags  # Store all tags for debugging
                
                # Log all metadata tags to see what's available
                logger.info(f"Video metadata tags: {json.dumps(format_tags, indent=2)}")
                
                # Try to get camera name from user-assigned name in title/description (most stable)
                camera_name_fields = ['title', 'description', 'artist', 'album', 'device_name', 'camera_name', 
                                    'com.ring.device_name', 'com.ring.camera_name']
                for key in camera_name_fields:
                    if key in format_tags and format_tags[key]:
                        detected_camera = format_tags[key].strip()
                        logger.info(f"Extracted camera name from metadata field '{key}': {detected_camera}")
                        break
                
                # If no camera name found in primary fields, try to parse device ID from comment as fallback
                if not detected_camera and 'comment' in format_tags:
                    device_id_full = format_tags['comment']
                    # Parse device ID: gml.{camera_id}.{session_id} -> extract camera_id
                    parts = device_id_full.split('.')
                    if len(parts) >= 2:
                        camera_id = parts[1]  # Get the middle part
                        if camera_id in RING_DEVICE_ID_MAP:
                            detected_camera = RING_DEVICE_ID_MAP[camera_id]
                            logger.info(f"Mapped camera ID '{camera_id}' (from '{device_id_full}') to camera: {detected_camera}")
                        else:
                            logger.warning(f"Unknown camera ID '{camera_id}' from full ID '{device_id_full}' - device ID rotation detected")
                            # Don't use the rotating ID - better to use "Unknown Camera"
                    else:
                        logger.warning(f"Could not parse device ID '{device_id_full}'")
                
                # Try to get creation_time from metadata (this should be the actual recording time)
                if 'creation_time' in format_tags:
                    metadata_time = format_tags['creation_time']
                    logger.info(f"Found creation_time in metadata: {metadata_time}")
                    # Parse the ISO timestamp and convert to local time if needed
                    try:
                        # Parse ISO format: 2025-11-23T07:22:36.000000Z
                        dt = datetime.fromisoformat(metadata_time.replace('Z', '+00:00'))
                        # Convert to local time string
                        recording_timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
                        logger.info(f"Converted metadata timestamp to: {recording_timestamp}")
                    except Exception as e:
                        logger.warning(f"Could not parse metadata timestamp: {e}")
                        # Keep the filename timestamp as fallback
                
                # If still no timestamp, try other metadata fields
                if not recording_timestamp:
                    for key in ['date', 'datetime', 'com.apple.quicktime.creationdate']:
                        if key in format_tags:
                            recording_timestamp = format_tags[key]
                            logger.info(f"Extracted recording timestamp from video metadata field '{key}': {recording_timestamp}")
                            break
        except Exception as e:
            logger.warning(f"Could not extract video metadata: {e}")
        
        # Open video for frame extraction
        cap = cv2.VideoCapture(str(video_save_path))
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Could not open video file")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_seconds = total_frames / fps if fps > 0 else 0
        
        # Add video to database
        video_id = db.add_video(
            filename=video.filename,
            camera_name=detected_camera or "Unknown Camera",
            duration=duration_seconds,
            fps=fps,
            total_frames=total_frames,
            video_path=str(video_save_path)
        )
        
        frames_extracted = 0
        detections_found = 0
        frame_records = []
        
        frame_num = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Only process every Nth frame based on sample_rate
            if frame_num % sample_rate == 0:
                # Save frame to disk
                frame_filename = f"{timestamp}_frame_{frame_num:06d}.jpg"
                frame_path = frames_dir / frame_filename
                cv2.imwrite(str(frame_path), frame)
                
                # Run detection on this frame
                detections, annotated = det.detect(frame, return_annotated=True)
                
                # Save annotated version if there are detections
                if detections:
                    annotated_filename = f"{timestamp}_frame_{frame_num:06d}_annotated.jpg"
                    annotated_path = frames_dir / annotated_filename
                    cv2.imwrite(str(annotated_path), annotated)
                    detections_found += 1
                
                # Add frame to database
                timestamp_in_video = frame_num / fps if fps > 0 else 0
                frame_id = db.add_frame(
                    video_id=video_id,
                    frame_number=frame_num,
                    timestamp_in_video=timestamp_in_video,
                    image_path=f"/api/training-frames/{frame_filename}",
                    has_detections=len(detections) > 0
                )
                
                # Add detections to database
                for detection in detections:
                    db.add_detection(
                        frame_id=frame_id,
                        bbox=detection['bbox'],
                        confidence=detection['confidence'],
                        class_name=detection.get('class_name', 'deer')
                    )
                
                # Also keep in memory for legacy compatibility (temporarily)
                max_conf = max([d['confidence'] for d in detections]) if detections else 0.0
                detection_record = {
                    "id": f"{timestamp}_frame_{frame_num}",
                    "timestamp": datetime.now().isoformat(),
                    "camera_name": "Manual Upload",
                    "zone_name": f"Video: {video.filename}",
                    "deer_count": len(detections) if detections else 0,
                    "confidence": max_conf,
                    "max_confidence": max_conf,
                    "irrigation_activated": False,
                    "image_path": f"/api/training-frames/{frame_filename}",
                    "annotated_image_path": f"/api/training-frames/{annotated_filename}" if detections else None,
                    "video_source": video_filename,
                    "frame_number": frame_num,
                    "timestamp_seconds": timestamp_in_video,
                    "detections": detections if detections else [],
                    "manual_annotations": [],
                    "reviewed": False,
                    "from_video_upload": True
                }
                
                detection_history.append(detection_record)
                frame_records.append(detection_record)
                frames_extracted += 1
            
            frame_num += 1
        
        cap.release()
        
        return {
            "success": True,
            "video_id": video_id,
            "video_filename": video_filename,
            "video_saved": str(video_save_path),
            "frames_extracted": frames_extracted,
            "detections_found": detections_found,
            "sample_rate": sample_rate,
            "fps": fps,
            "total_frames": total_frames,
            "duration_seconds": duration_seconds,
            "recording_timestamp": recording_timestamp,
            "detected_camera": detected_camera,
            "video_metadata": video_metadata,
            "message": f"Video processed: {frames_extracted} frames extracted (every {sample_rate} frame{'s' if sample_rate > 1 else ''}), {detections_found} with detections"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")
    finally:
        await video.close()


@app.get("/api/training-frames/{frame_name}")
async def get_training_frame(frame_name: str):
    """Serve training frames."""
    # Frames are stored in data/frames/ directory
    frame_path = Path("data/frames") / frame_name
    if not frame_path.exists():
        # Also try training_frames directory for backward compatibility
        frame_path = Path("data/training_frames") / frame_name
        if not frame_path.exists():
            logger.error(f"Frame not found: {frame_name}")
            raise HTTPException(status_code=404, detail="Frame not found")
    return FileResponse(frame_path)


@app.get("/api/frames/{frame_id}/annotated")
async def get_annotated_frame(frame_id: int):
    """Get frame with bounding boxes drawn for all detections."""
    if not CV2_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCV not available")
    
    frame = db.get_frame(frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame not found")
    
    # Get the original frame path
    image_path = frame.get('image_path', '')
    
    # Handle different path formats
    if image_path.startswith('/api/training-frames/'):
        # URL format: /api/training-frames/filename.jpg
        frame_filename = image_path.replace('/api/training-frames/', '')
        frame_path = Path("data/frames") / frame_filename
        # Legacy frames may still be in training_frames during migration
        if not frame_path.exists():
            frame_path = Path("data/training_frames") / frame_filename
    elif image_path.startswith('data/'):
        # Direct path format: data/frames/filename.jpg or data/training_frames/filename.jpg
        frame_path = Path(image_path)
    else:
        raise HTTPException(status_code=404, detail=f"Unsupported frame path format: {image_path}")
    
    if not frame_path.exists():
        logger.error(f"Frame file not found: {frame_path}")
        raise HTTPException(status_code=404, detail="Frame file not found")
    
    # Check if annotated version already exists
    annotated_path = frame_path.parent / frame_path.name.replace('.jpg', '_annotated.jpg')
    if annotated_path.exists():
        return FileResponse(annotated_path, media_type="image/jpeg")
    
    # Generate annotated frame on the fly
    import cv2
    import numpy as np
    
    img = cv2.imread(str(frame_path))
    if img is None:
        raise HTTPException(status_code=500, detail="Could not read frame")
    
    # Draw detections
    detections = frame.get('detections', [])
    for det in detections:
        x1 = int(det['bbox_x1'])
        y1 = int(det['bbox_y1'])
        x2 = int(det['bbox_x2'])
        y2 = int(det['bbox_y2'])
        confidence = det['confidence']
        
        # Draw bounding box
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        # Draw label
        label = f"deer {confidence:.2f}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 2
        
        # Get text size for background
        (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
        
        # Draw background rectangle
        cv2.rectangle(img, (x1, y1 - text_height - 10), (x1 + text_width, y1), (0, 255, 0), -1)
        
        # Draw text
        cv2.putText(img, label, (x1, y1 - 5), font, font_scale, (0, 0, 0), thickness)
    
    # Draw manual annotations
    annotations = frame.get('annotations', [])
    for ann in annotations:
        # Convert normalized coordinates to pixel coordinates
        img_height, img_width = img.shape[:2]
        x_center = int(ann['x'] * img_width)
        y_center = int(ann['y'] * img_height)
        width = int(ann['width'] * img_width)
        height = int(ann['height'] * img_height)
        
        x1 = x_center - width // 2
        y1 = y_center - height // 2
        x2 = x_center + width // 2
        y2 = y_center + height // 2
        
        # Draw manual annotation in blue
        cv2.rectangle(img, (x1, y1), (x2, y2), (255, 0, 0), 2)
        cv2.putText(img, "manual", (x1, y1 - 5), font, 0.5, (255, 0, 0), 1)
    
    # Save annotated version for future use
    cv2.imwrite(str(annotated_path), img)
    
    return FileResponse(annotated_path, media_type="image/jpeg")


@app.post("/api/frames/{frame_id}/review")
async def review_frame(frame_id: int, request: dict):
    """Mark a frame as reviewed."""
    review_type = request.get('review_type', 'correct')
    
    # Update frame review status
    db.update_frame_review(frame_id, reviewed=True, review_type=review_type)
    
    # If marked as correct or corrected, mark it for training
    if review_type in ['correct', 'corrected']:
        db.mark_frame_for_training(frame_id)
    
    return {"success": True, "frame_id": frame_id, "review_type": review_type}


@app.post("/api/frames/{frame_id}/annotate")
async def annotate_frame(frame_id: int, request: dict):
    """Add manual annotations to a frame. Replaces all existing annotations."""
    annotations = request.get('annotations', [])
    
    # Get frame to ensure it exists
    frame = db.get_frame(frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame not found")
    
    # CRITICAL: Delete all existing annotations first to avoid duplicates
    db.delete_annotations_for_frame(frame_id)
    
    # Save new annotations
    for ann in annotations:
        bbox = {
            'x': ann['x'],
            'y': ann['y'],
            'width': ann['width'],
            'height': ann['height']
        }
        db.add_annotation(
            frame_id=frame_id,
            bbox=bbox,
            annotation_type='addition',
            annotator='user'
        )
    
    return {"success": True, "frame_id": frame_id, "annotation_count": len(annotations)}


@app.delete("/api/frames/{frame_id}")
async def delete_frame(frame_id: int):
    """Delete a frame and its associated data."""
    frame = db.get_frame(frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame not found")
    
    # Delete the frame record (cascade will delete detections and annotations)
    db.delete_frame(frame_id)
    
    return {"success": True, "frame_id": frame_id}


@app.get("/app/snapshots/{snapshot_name}")
async def get_snapshot(snapshot_name: str):
    """Serve snapshot images from coordinator"""
    from fastapi.responses import FileResponse
    
    # Snapshots are mounted to host at ./dell-deployment/data/snapshots
    snapshot_path = Path(__file__).parent.parent / "dell-deployment" / "data" / "snapshots" / snapshot_name
    
    if not snapshot_path.exists():
        logger.error(f"Snapshot not found: {snapshot_path}")
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    return FileResponse(
        path=str(snapshot_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=3600"}
    )


@app.get("/api/images/{image_name}")
async def get_detection_image(image_name: str):
    """Serve detection images."""
    image_path = Path("temp/demo_detections") / image_name
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await websocket.accept()
    active_websockets.append(websocket)
    
    try:
        # Send initial state
        await websocket.send_json({
            "type": "connected",
            "stats": stats,
            "settings": settings.dict()
        })
        
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            # Echo for now (can add commands later)
            await websocket.send_text(f"Echo: {data}")
    
    except WebSocketDisconnect:
        active_websockets.remove(websocket)


async def broadcast_message(message: dict):
    """Broadcast message to all connected WebSocket clients."""
    for ws in active_websockets:
        try:
            await ws.send_json(message)
        except:
            pass


def is_in_season() -> bool:
    """Check if current date is within irrigation season."""
    now = datetime.now()
    start_month, start_day = map(int, settings.season_start.split('-'))
    end_month, end_day = map(int, settings.season_end.split('-'))
    
    season_start = datetime(now.year, start_month, start_day)
    season_end = datetime(now.year, end_month, end_day)
    
    if season_start > season_end:
        return now >= season_start or now <= season_end
    else:
        return season_start <= now <= season_end


@app.post("/api/demo/load")
async def load_demo_data():
    """Generate synthetic demo detection data for testing.
    
    TODO: Replace with actual training images from Google Drive.
    Images are stored in: Google Drive > 'Deer video detection' > videos/annotations/images/
    Could sync sample images locally or use Drive API to fetch them.
    """
    global detection_history, stats
    
    # Clear existing data
    detection_history = []
    stats["total_detections"] = 0
    stats["total_deer"] = 0
    stats["irrigation_activated"] = 0
    
    # Generate synthetic demo data
    camera_names = ["Front Camera", "Side Camera", "Driveway Camera", "Backyard Camera"]
    zone_names = ["Driveway North", "Garage North", "Front Beds", "Woods North", "Patio Lawn"]
    
    # Create 15 demo detections over the past 7 days
    for i in range(15):
        # Vary the time - spread over past 7 days with more recent activity
        hours_ago = (i * 12) % 168  # Spread over 7 days (168 hours)
        timestamp = (datetime.now() - timedelta(hours=hours_ago)).isoformat()
        
        deer_count = 1 + (i % 3)  # 1-3 deer
        confidence = 0.65 + (i % 7) * 0.05  # 0.65-0.95 confidence
        
        detection_history.append({
            "timestamp": timestamp,
            "camera_name": camera_names[i % len(camera_names)],
            "zone_name": zone_names[i % len(zone_names)],
            "deer_count": deer_count,
            "max_confidence": confidence,
            "image_path": None,  # No actual image for synthetic data
            "irrigation_activated": not settings.dry_run
        })
        
        stats["total_detections"] += 1
        stats["total_deer"] += deer_count
        if not settings.dry_run:
            stats["irrigation_activated"] += 1
    
    # Sort by timestamp (most recent first)
    detection_history.sort(key=lambda x: x["timestamp"], reverse=True)
    
    stats["last_detection"] = detection_history[0]["timestamp"] if detection_history else None
    
    # Broadcast update
    await broadcast_message({
        "type": "demo_data_loaded",
        "count": len(detection_history)
    })
    
    return {
        "status": "loaded",
        "detections": len(detection_history),
        "stats": stats
    }


@app.post("/api/demo/clear")
async def clear_demo_data():
    """Clear all detection data and reset to live mode."""
    global detection_history, stats
    
    # Clear all data
    detection_history = []
    stats["total_detections"] = 0
    stats["total_deer"] = 0
    stats["irrigation_activated"] = 0
    stats["last_detection"] = None
    
    # Broadcast update
    await broadcast_message({
        "type": "demo_data_cleared"
    })
    
    return {
        "status": "cleared",
        "message": "All detection data cleared. System ready for live detections."
    }


@app.post("/api/detections/{detection_id}/review")
async def review_detection(detection_id: str, review: DetectionReview):
    """Submit a review/label for a detection to improve training data."""
    global detection_reviews
    
    # Find the detection
    detection = next(
        (d for i, d in enumerate(detection_history) if f"det-{i}" == detection_id),
        None
    )
    
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    
    # Store review with timestamp
    review_data = review.dict()
    review_data["reviewed_at"] = datetime.now().isoformat()
    review_data["detection"] = detection
    detection_reviews[detection_id] = review_data
    
    print(f"📝 Detection {detection_id} reviewed as: {review.review_type}")
    
    # Broadcast update
    await broadcast_message({
        "type": "detection_reviewed",
        "detection_id": detection_id,
        "review_type": review.review_type
    })
    
    return {
        "status": "success",
        "detection_id": detection_id,
        "review_type": review.review_type,
        "total_reviews": len(detection_reviews)
    }


@app.get("/api/detections/{detection_id}/review")
async def get_detection_review(detection_id: str):
    """Get review status for a detection."""
    if detection_id not in detection_reviews:
        return {"status": "not_reviewed", "detection_id": detection_id}
    
    return {
        "status": "reviewed",
        "detection_id": detection_id,
        **detection_reviews[detection_id]
    }


@app.post("/api/detections/{detection_id}/annotate")
async def save_manual_annotations(detection_id: str, payload: dict):
    """
    Save manual bounding box annotations for a detection.
    Used when user draws boxes around missed deer.
    
    Args:
        detection_id: The detection ID
        payload: {
            bounding_boxes: [{"x": int, "y": int, "width": int, "height": int}, ...],
            deer_count: int,
            annotator: str
        }
    """
    # Find the detection in history
    detection = None
    for d in detection_history:
        if d.get("id") == detection_id:
            detection = d
            break
    
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    
    # Save annotations
    detection["manual_annotations"] = payload.get("bounding_boxes", [])
    detection["deer_count"] = payload.get("deer_count", len(payload.get("bounding_boxes", [])))
    detection["annotated_by"] = payload.get("annotator", "user")
    detection["annotated_at"] = datetime.now().isoformat()
    
    return {
        "status": "success",
        "detection_id": detection_id,
        "annotations_saved": len(payload.get("bounding_boxes", [])),
        "deer_count": detection["deer_count"]
    }


@app.patch("/api/detections/{detection_id}/camera")
async def update_detection_camera(detection_id: str, camera_name: str):
    """Update the camera name for a detection."""
    global detection_history
    
    # Find the detection
    detection = None
    for d in detection_history:
        if d["id"] == detection_id:
            detection = d
            break
    
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    
    # Update camera name
    detection["camera_name"] = camera_name
    
    return {
        "status": "success",
        "detection_id": detection_id,
        "camera_name": camera_name
    }


@app.delete("/api/detections/{detection_id}")
async def delete_detection(detection_id: str):
    """Delete a detection from the review queue."""
    global detection_history
    
    # Find the detection
    detection = None
    detection_index = None
    for i, d in enumerate(detection_history):
        if d["id"] == detection_id:
            detection = d
            detection_index = i
            break
    
    if not detection:
        raise HTTPException(status_code=404, detail="Detection not found")
    
    # Delete the image file if it exists
    if detection.get("image_path"):
        try:
            image_path = Path(detection["image_path"])
            if image_path.exists():
                image_path.unlink()
        except Exception as e:
            print(f"Warning: Could not delete image file: {e}")
    
    # Remove from detection_history
    detection_history.pop(detection_index)
    
    return {
        "status": "success",
        "detection_id": detection_id,
        "message": "Detection deleted"
    }


@app.post("/api/detections/batch-delete")
async def batch_delete_detections(detection_ids: List[str]):
    """Delete multiple detections at once."""
    global detection_history
    
    deleted_count = 0
    errors = []
    
    for detection_id in detection_ids:
        try:
            # Find the detection
            detection = None
            detection_index = None
            for i, d in enumerate(detection_history):
                if d["id"] == detection_id:
                    detection = d
                    detection_index = i
                    break
            
            if detection:
                # Delete the image file if it exists
                if detection.get("image_path"):
                    try:
                        image_path = Path(detection["image_path"])
                        if image_path.exists():
                            image_path.unlink()
                    except Exception as e:
                        print(f"Warning: Could not delete image file: {e}")
                
                # Remove from detection_history
                detection_history.pop(detection_index)
                deleted_count += 1
            else:
                errors.append(f"Detection {detection_id} not found")
        except Exception as e:
            errors.append(f"Error deleting {detection_id}: {str(e)}")
    
    return {
        "status": "success" if deleted_count > 0 else "error",
        "deleted_count": deleted_count,
        "errors": errors if errors else None
    }


@app.post("/api/detections/missed")
async def report_missed_detection(report: MissedDetection):
    """Report a detection that was missed by the ML model."""
    missed_report = {
        "id": f"missed-{len(missed_detections)+1}",
        "timestamp": report.timestamp,
        "camera_name": report.camera_name,
        "deer_count": report.deer_count,
        "notes": report.notes,
        "reporter": report.reporter,
        "reported_at": datetime.now().isoformat()
    }
    
    missed_detections.append(missed_report)
    
    # Broadcast to websockets
    await broadcast_message({
        "type": "missed_detection_reported",
        "report": missed_report
    })
    
    return {
        "status": "success",
        "message": "Missed detection reported",
        "report_id": missed_report["id"],
        "total_missed": len(missed_detections)
    }


@app.get("/api/detections/missed")
async def get_missed_detections():
    """Get all reported missed detections."""
    return {
        "total": len(missed_detections),
        "reports": missed_detections
    }


@app.get("/api/training/stats")
async def get_training_stats():
    """Get training and review statistics from database."""
    stats = db.get_training_statistics()
    return stats


# Video Library Endpoints
@app.get("/api/videos")
async def get_videos():
    """Get all uploaded videos with metadata."""
    videos = db.get_all_videos()
    
    logger.info(f"=== GET VIDEOS - Returning {len(videos)} videos ===")
    for video in videos:
        logger.info(f"Video ID: {video.get('id')}, Filename: {video.get('filename')}")
    
    # Check annotation status for each video
    for video in videos:
        video_id = video['id']
        # Check if any frames have annotations (partial)
        has_annotations = db.video_has_annotations(video_id)
        video['has_annotations'] = has_annotations
        # Check if ALL frames are annotated/reviewed (complete)
        fully_annotated = db.video_fully_annotated(video_id)
        video['fully_annotated'] = fully_annotated
    
    return videos


@app.get("/api/debug/status")
async def get_debug_status():
    """Diagnostic endpoint: Show current system state."""
    videos = db.get_all_videos()
    
    # Get frame counts using database connection
    conn = db.get_connection()
    all_frames = conn.execute("SELECT COUNT(*) FROM frames").fetchone()[0]
    training_frames = conn.execute("SELECT COUNT(*) FROM frames WHERE selected_for_training = 1").fetchone()[0]
    
    # Get per-video frame counts
    video_frames = []
    for video in videos:
        vid = video['id']
        total = conn.execute("SELECT COUNT(*) FROM frames WHERE video_id = ?", (vid,)).fetchone()[0]
        training = conn.execute("SELECT COUNT(*) FROM frames WHERE video_id = ? AND selected_for_training = 1", (vid,)).fetchone()[0]
        video_frames.append({
            "video_id": vid,
            "filename": video['filename'],
            "total_frames": total,
            "training_frames": training
        })
    
    return {
        "total_videos": len(videos),
        "video_ids": [v['id'] for v in videos],
        "total_frames": all_frames,
        "training_frames": training_frames,
        "video_frame_details": video_frames,
        "videos": videos[:3]  # First 3 videos with full details
    }


@app.get("/api/videos/device-ids")
async def get_video_device_ids():
    """
    Diagnostic endpoint: Show which device ID is in each video file.
    """
    videos = db.get_all_videos()
    results = []
    
    for video in videos:
        try:
            video_path = Path(video.get('video_path', ''))
            if not video_path.exists():
                continue
            
            import subprocess
            import json
            
            result = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', str(video_path)],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                metadata = json.loads(result.stdout)
                format_tags = metadata.get('format', {}).get('tags', {})
                device_id = format_tags.get('comment', 'NO_DEVICE_ID')
                
                results.append({
                    "id": video['id'],
                    "filename": video['filename'],
                    "device_id": device_id,
                    "current_camera_name": video.get('camera_name'),
                    "mapped_name": RING_DEVICE_ID_MAP.get(device_id, "UNKNOWN")
                })
        
        except Exception as e:
            results.append({
                "id": video['id'],
                "filename": video['filename'],
                "error": str(e)
            })
    
    return results


@app.get("/api/videos/archived")
async def get_archived_videos_endpoint():
    """Get all archived videos with annotation status."""
    videos = db.get_archived_videos()
    
    # Add annotation status for each video
    for video in videos:
        video_id = video['id']
        fully_annotated = db.video_fully_annotated(video_id)
        has_annotations = db.video_has_annotations(video_id)
        video['fully_annotated'] = fully_annotated
        video['has_annotations'] = has_annotations
    
    return videos


@app.get("/api/videos/{video_id}")
async def get_video_details(video_id: int):
    """Get detailed information about a specific video."""
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Get frames for this video
    frames = db.get_frames_for_video(video_id)
    video['frames'] = frames
    
    return video


@app.delete("/api/videos/{video_id}")
async def delete_video_endpoint(video_id: int):
    """Delete a video and all associated data."""
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Delete video file if it exists
    if video.get('video_path'):
        video_path = Path(video['video_path'])
        if video_path.exists():
            video_path.unlink()
    
    # Delete from database (cascades to frames, detections, annotations)
    db.delete_video(video_id)
    
    return {"status": "success", "message": "Video deleted"}


@app.post("/api/videos/{video_id}/archive")
async def archive_video_endpoint(video_id: int):
    """Archive a video (hides from main gallery but preserves all data)."""
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    success = db.archive_video(video_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to archive video")
    
    return {"status": "success", "message": "Video archived"}


@app.post("/api/videos/{video_id}/unarchive")
async def unarchive_video_endpoint(video_id: int):
    """Unarchive a video (restore to main gallery)."""
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    success = db.unarchive_video(video_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to unarchive video")
    
    return {"status": "success", "message": "Video unarchived"}


@app.post("/api/videos/reanalyze-all")
async def reanalyze_all_videos():
    """Re-analyze all videos with the updated model."""
    try:
        # Load detector with production model
        detector = load_detector()
        if detector is None:
            raise HTTPException(status_code=500, detail="Detector not available")
        
        # Get all non-archived videos
        videos = db.get_all_videos()
        videos = [v for v in videos if not v.get('archived')]
        
        processed = 0
        total_detections = 0
        project_root = Path(__file__).parent.parent
        
        for video in videos:
            video_id = video['id']
            
            # Get all frames for this video
            frames = db.get_frames_for_video(video_id)
            
            # Re-run detection on each frame
            for frame in frames:
                # Convert image_path from API format to actual file path
                image_path = frame.get('image_path', '')
                if image_path.startswith('/api/training-frames/'):
                    frame_filename = image_path.replace('/api/training-frames/', '')
                    frame_path = project_root / "data" / "frames" / frame_filename
                    # Legacy: check training_frames if not found in frames
                    if not frame_path.exists():
                        frame_path = project_root / "data" / "training_frames" / frame_filename
                elif image_path.startswith('data/'):
                    frame_path = project_root / image_path
                else:
                    continue
                
                if not frame_path.exists():
                    continue
                
                # Load frame image
                frame_img = cv2.imread(str(frame_path))
                if frame_img is None:
                    continue
                
                # Run detection
                detections, _ = detector.detect(frame_img)
                
                # Delete old detections for this frame
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM detections WHERE frame_id = ?", (frame['id'],))
                conn.commit()
                conn.close()
                
                # Add new detections
                for det in detections:
                    bbox = {
                        'x1': int(det['bbox']['x1']),
                        'y1': int(det['bbox']['y1']),
                        'x2': int(det['bbox']['x2']),
                        'y2': int(det['bbox']['y2'])
                    }
                    db.add_detection(
                        frame_id=frame['id'],
                        bbox=bbox,
                        confidence=float(det['confidence']),
                        class_name='deer'
                    )
                    total_detections += 1
            
            processed += 1
        
        logger.info(f"Re-analyzed {processed} videos, found {total_detections} detections")
        
        return {
            "status": "success",
            "processed": processed,
            "total_detections": total_detections
        }
        
    except Exception as e:
        logger.error(f"Re-analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/videos/{video_id}")
async def update_video_metadata(video_id: int, request: dict):
    """Update video metadata (camera and/or capture timestamp)."""
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Extract camera and captured_at from request body
    camera = request.get('camera')
    captured_at = request.get('captured_at')
    
    # Update video metadata in database
    db.update_video_metadata(video_id, camera=camera, captured_at=captured_at)
    
    return {"status": "success", "message": "Video metadata updated"}


@app.get("/api/videos/{video_id}/stream")
async def stream_video(video_id: int):
    """Stream a video file."""
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video_path = Path(video.get('video_path', ''))
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    return FileResponse(video_path, media_type="video/mp4")


@app.get("/api/videos/{video_id}/thumbnail")
async def get_video_thumbnail(video_id: int):
    """Get thumbnail (first frame) of a video."""
    if not CV2_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCV not available")
    
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video_path = Path(video.get('video_path', ''))
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    # Check if thumbnail already exists
    thumbnail_dir = Path("data/thumbnails")
    thumbnail_dir.mkdir(parents=True, exist_ok=True)
    thumbnail_path = thumbnail_dir / f"video_{video_id}_thumb.jpg"
    
    if thumbnail_path.exists():
        return FileResponse(thumbnail_path, media_type="image/jpeg")
    
    # Generate thumbnail from first frame
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Could not open video file")
    
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        raise HTTPException(status_code=500, detail="Could not extract frame from video")
    
    # Resize to thumbnail size (maintaining aspect ratio)
    height, width = frame.shape[:2]
    max_width = 320
    if width > max_width:
        ratio = max_width / width
        new_width = max_width
        new_height = int(height * ratio)
        frame = cv2.resize(frame, (new_width, new_height))
    
    # Save thumbnail
    cv2.imwrite(str(thumbnail_path), frame)
    
    return FileResponse(thumbnail_path, media_type="image/jpeg")


@app.get("/api/videos/{video_id}/has-frames")
async def check_video_has_frames(video_id: int):
    """Check if a video already has extracted frames for training."""
    logger.info(f"=== CHECKING FRAMES FOR VIDEO {video_id} ===")
    
    video = db.get_video(video_id)
    if not video:
        logger.error(f"Video {video_id} NOT FOUND in database!")
        raise HTTPException(status_code=404, detail="Video not found")
    
    logger.info(f"Video found: {video.get('filename')}")
    
    # Get frames for this video that are marked for training
    frames = db.get_frames_for_video(video_id)
    training_frames = [f for f in frames if f.get('selected_for_training', 0) == 1]
    
    logger.info(f"Total frames for video: {len(frames)}, Training frames: {len(training_frames)}")
    
    result = {
        "has_frames": len(training_frames) > 0,
        "frame_count": len(training_frames),
        "video_id": video_id
    }
    
    logger.info(f"Returning: {result}")
    
    return result


@app.delete("/api/training/frames/clear-all")
async def clear_all_training_frames():
    """Delete ALL training frames from all videos - fresh start."""
    # Get all frames marked for training
    all_frames = db.get_training_frames()
    deleted_count = 0
    
    for frame in all_frames:
        db.delete_frame(frame['id'])
        deleted_count += 1
    
    logger.info(f"Cleared all training frames: {deleted_count} frames deleted")
    
    return {
        "status": "success",
        "frames_deleted": deleted_count,
        "message": f"Deleted {deleted_count} training frames"
    }


@app.delete("/api/videos/{video_id}/clear-frames")
async def clear_video_training_frames(video_id: int):
    """Delete training frames for a specific video."""
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    try:
        # Get frames for this video
        frames = db.get_frames_for_video(video_id)
        deleted_count = 0
        
        for frame in frames:
            if frame.get('selected_for_training', 0) == 1:
                try:
                    db.delete_frame(frame['id'])
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting frame {frame['id']}: {e}")
        
        logger.info(f"Cleared {deleted_count} training frames for video {video_id}")
        
        return {
            "status": "success",
            "video_id": video_id,
            "frames_deleted": deleted_count,
            "message": f"Deleted {deleted_count} training frames from video"
        }
    except Exception as e:
        logger.error(f"Error clearing frames for video {video_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/videos/{video_id}/extract-frames")
async def extract_frames_from_video(video_id: int, request: dict):
    """Extract frames from a specific video for annotation."""
    if not CV2_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCV not available")
    
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video_path = Path(video.get('video_path', ''))
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    sampling_rate = request.get('sampling_rate', 'medium')
    
    logger.info(f"Starting frame extraction for video {video_id} with sampling rate: {sampling_rate}")
    
    # CRITICAL: Delete ALL existing training frames for this video before extracting
    # This prevents accumulation from multiple extraction runs
    existing_frames = db.get_frames_for_video(video_id)
    training_frame_ids = [f['id'] for f in existing_frames if f.get('selected_for_training', 0) == 1]
    
    logger.info(f"Found {len(training_frame_ids)} existing training frames to delete for video {video_id}")
    
    deleted_count = 0
    for frame_id in training_frame_ids:
        try:
            success = db.delete_frame(frame_id)
            if success:
                deleted_count += 1
        except Exception as e:
            logger.error(f"Error deleting frame {frame_id}: {e}")
    
    logger.info(f"Deleted {deleted_count} training frames for video {video_id}")
    
    # Handle both string and numeric sampling rates
    if isinstance(sampling_rate, (int, float)):
        # Numeric value is frame_interval directly
        frame_interval = int(sampling_rate)
    else:
        # Map sampling rate to frame interval (in frames)
        # At 30fps: 0.5s=15, 1s=30, 2s=60, 5s=150
        rate_map = {
            'high': 15,       # ~2 frames per second
            'medium': 30,     # 1 frame per second  
            'low': 60,        # 1 frame per 2 seconds
            'sparse': 150     # 1 frame per 5 seconds
        }
        frame_interval = rate_map.get(sampling_rate, 30)
    
    # Extract frames
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Could not open video file")
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    logger.info(f"Video properties: {frame_count} frames at {fps} fps")
    
    frames_dir = Path("data/frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    
    extracted_count = 0
    frame_number = 0
    
    # Use cv2.CAP_PROP_POS_FRAMES to seek to specific frames instead of reading sequentially
    # This prevents issues with video codecs that might loop or have bad frame counts
    frames_to_extract = list(range(0, frame_count, frame_interval))
    
    logger.info(f"Planning to extract {len(frames_to_extract)} frames at interval {frame_interval}")
    
    for target_frame in frames_to_extract:
        # Seek to the specific frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        ret, frame = cap.read()
        
        if not ret:
            logger.warning(f"Failed to read frame {target_frame}, stopping extraction")
            break
        
        # Verify we're at the correct frame position
        actual_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES)) - 1
        if actual_pos != target_frame:
            logger.warning(f"Frame position mismatch: requested {target_frame}, got {actual_pos}")
        
        # Save frame
        frame_filename = f"video_{video_id}_frame_{target_frame}.jpg"
        frame_path = frames_dir / frame_filename
        cv2.imwrite(str(frame_path), frame)
        
        # Calculate timestamp
        timestamp_sec = target_frame / fps
        
        # Store in database
        frame_id = db.add_frame(
            video_id=video_id,
            frame_number=target_frame,
            timestamp_in_video=timestamp_sec,
            image_path=str(frame_path),
            has_detections=False
        )
        # Mark as selected for training so it appears in review
        db.mark_frame_for_training(frame_id)
        extracted_count += 1
    
    cap.release()
    
    logger.info(f"Extraction complete: {extracted_count} frames from video {video_id}, interval: every {frame_interval} frames")
    logger.info(f"Video stats: {frame_count} total frames at {fps} fps")
    
    # Run detection on the extracted frames
    logger.info(f"Running detection on {extracted_count} extracted frames...")
    detector = load_detector()
    
    if not detector:
        logger.error("Detector not loaded! Cannot run automatic detection")
        detections_found = 0
    else:
        logger.info("Detector loaded successfully")
        # Get the frames we just extracted
        all_frames = db.get_frames_for_video(video_id)
        newly_extracted = [f for f in all_frames if f.get('selected_for_training', 0) == 1]
        
        logger.info(f"Found {len(newly_extracted)} frames marked for training")
        
        detections_found = 0
        total_detections = 0
        
        for i, frame in enumerate(newly_extracted):
            frame_path = Path(frame['image_path'])
            if not frame_path.exists():
                logger.warning(f"Frame file not found: {frame_path}")
                continue
            
            # Read frame and run detection
            try:
                frame_img = cv2.imread(str(frame_path))
                if frame_img is None:
                    logger.warning(f"Could not read frame: {frame_path}")
                    continue
                
                logger.debug(f"Running detection on frame {i+1}/{len(newly_extracted)}: {frame['id']}")
                detections, _ = detector.detect(frame_img, return_annotated=False)
                
                logger.debug(f"Frame {frame['id']}: {len(detections)} detections found")
                
                # Store detections in database
                if detections:
                    detections_found += 1
                    for det in detections:
                        bbox = det['bbox']
                        
                        db.add_detection(
                            frame_id=frame['id'],
                            bbox=bbox,
                            confidence=det['confidence'],
                            class_name=det.get('class_name', 'deer')
                        )
                        total_detections += 1
                        logger.debug(f"Added detection: bbox={bbox}, conf={det['confidence']}")
            except Exception as e:
                logger.error(f"Error processing frame {frame['id']}: {e}", exc_info=True)
        
        logger.info(f"Detection complete: {detections_found}/{len(newly_extracted)} frames with deer ({total_detections} total detections)")
        detections_found = total_detections
    
    return {
        "status": "success",
        "video_id": video_id,
        "frames_extracted": extracted_count,
        "total_frames": frame_count,
        "sampling_rate": sampling_rate,
        "frame_interval": frame_interval,
        "detections_found": detections_found
    }


@app.post("/api/videos/{video_id}/fill-missing-frames")
async def fill_missing_frames(video_id: int):
    """
    Fill in missing frames that weren't extracted due to buggy frame sampling.
    This preserves all existing frames and annotations, only adding the gaps.
    """
    if not CV2_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCV not available")
    
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video_path = Path(video.get('video_path', ''))
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    
    logger.info(f"Starting missing frame fill for video {video_id}")
    
    # Get existing frames to find the gaps
    existing_frames = db.get_frames_for_video(video_id)
    if not existing_frames:
        raise HTTPException(status_code=400, detail="No existing frames found")
    
    # Get all existing frame numbers
    existing_frame_numbers = sorted([f['frame_number'] for f in existing_frames])
    logger.info(f"Found {len(existing_frame_numbers)} existing frames: {existing_frame_numbers[:20]}...")
    
    # Determine the frame interval by looking at the pattern
    # Find the most common gap between consecutive frames
    gaps = []
    for i in range(len(existing_frame_numbers) - 1):
        gap = existing_frame_numbers[i + 1] - existing_frame_numbers[i]
        if gap > 0:
            gaps.append(gap)
    
    if not gaps:
        return {"status": "success", "message": "No gaps to fill", "frames_added": 0}
    
    # The frame interval should be close to the minimum gap
    from collections import Counter
    gap_counts = Counter(gaps)
    frame_interval = min(gap_counts.keys())
    logger.info(f"Detected frame interval: {frame_interval}, gap distribution: {dict(gap_counts)}")
    
    # Find all missing frame numbers within the range
    min_frame = min(existing_frame_numbers)
    max_frame = max(existing_frame_numbers)
    
    expected_frames = set(range(min_frame, max_frame + 1, frame_interval))
    existing_set = set(existing_frame_numbers)
    missing_frames = sorted(expected_frames - existing_set)
    
    logger.info(f"Found {len(missing_frames)} missing frames: {missing_frames[:20]}...")
    
    if not missing_frames:
        return {"status": "success", "message": "No missing frames found", "frames_added": 0}
    
    # Extract the missing frames
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Could not open video file")
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frames_dir = Path("data/frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    
    added_count = 0
    
    for frame_number in missing_frames:
        # Seek to the specific frame
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        
        if not ret:
            logger.warning(f"Could not read frame {frame_number}")
            continue
        
        # Save frame
        frame_filename = f"video_{video_id}_frame_{frame_number}.jpg"
        frame_path = frames_dir / frame_filename
        cv2.imwrite(str(frame_path), frame)
        
        # Calculate timestamp
        timestamp_sec = frame_number / fps
        
        # Store in database
        frame_id = db.add_frame(
            video_id=video_id,
            frame_number=frame_number,
            timestamp_in_video=timestamp_sec,
            image_path=str(frame_path),
            has_detections=False
        )
        # Mark as selected for training
        db.mark_frame_for_training(frame_id)
        added_count += 1
    
    cap.release()
    
    logger.info(f"Fill complete: added {added_count} missing frames to video {video_id}")
    
    return {
        "status": "success",
        "video_id": video_id,
        "frames_added": added_count,
        "missing_frames": missing_frames
    }


@app.post("/api/videos/fix-camera-names")
async def fix_camera_names():
    """
    Re-extract camera names from video metadata for all existing videos.
    This will update videos that were uploaded before the camera detection was working.
    """
    videos = db.get_all_videos()
    fixed_count = 0
    errors = []
    
    for video in videos:
        try:
            video_path = Path(video.get('video_path', ''))
            if not video_path.exists():
                errors.append(f"Video {video['id']}: file not found")
                continue
            
            # Extract metadata using ffprobe
            import subprocess
            import json
            
            result = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', str(video_path)],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                metadata = json.loads(result.stdout)
                format_tags = metadata.get('format', {}).get('tags', {})
                
                detected_camera = None
                
                # Check for manual override first
                if video['filename'] in VIDEO_CAMERA_OVERRIDES:
                    detected_camera = VIDEO_CAMERA_OVERRIDES[video['filename']]
                    logger.info(f"Video {video['id']}: Using manual override for '{video['filename']}' -> {detected_camera}")
                # Try to get camera name from Ring device ID in comment field
                elif 'comment' in format_tags:
                    device_id_full = format_tags['comment']
                    # Parse device ID: gml.{camera_id}.{session_id} -> extract camera_id
                    parts = device_id_full.split('.')
                    if len(parts) >= 2:
                        camera_id = parts[1]  # Get the middle part
                        if camera_id in RING_DEVICE_ID_MAP:
                            detected_camera = RING_DEVICE_ID_MAP[camera_id]
                            logger.info(f"Video {video['id']}: Mapped camera ID '{camera_id}' (from '{device_id_full}') to camera: {detected_camera}")
                        else:
                            detected_camera = device_id_full
                            logger.warning(f"Video {video['id']}: Unknown camera ID '{camera_id}' from full ID '{device_id_full}'")
                    else:
                        detected_camera = device_id_full
                        logger.warning(f"Video {video['id']}: Could not parse device ID '{device_id_full}'")
                
                # If we found a camera name, update the database
                if detected_camera and detected_camera != video.get('camera_name'):
                    db.update_video_camera_name(video['id'], detected_camera)
                    fixed_count += 1
                    logger.info(f"Updated video {video['id']} camera from '{video.get('camera_name')}' to '{detected_camera}'")
        
        except Exception as e:
            errors.append(f"Video {video['id']}: {str(e)}")
            logger.error(f"Error fixing camera name for video {video['id']}: {e}")
    
    return {
        "status": "success",
        "total_videos": len(videos),
        "fixed_count": fixed_count,
        "errors": errors if errors else None
    }


@app.post("/api/videos/fill-all-missing-frames")
async def fill_all_missing_frames():
    """
    ONE-TIME MIGRATION: Fill in missing frames for all videos.
    This processes every video that has existing frames and fills in the gaps
    caused by buggy frame sampling, while preserving all annotations.
    """
    if not CV2_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCV not available")
    
    videos = db.get_all_videos()
    processed = 0
    updated = 0
    errors = []
    details = []
    
    for video in videos:
        video_id = video['id']
        
        # Only process videos that have frames
        existing_frames = db.get_frames_for_video(video_id)
        if not existing_frames:
            continue
        
        processed += 1
        
        try:
            # Call the existing fill-missing-frames logic
            result = await fill_missing_frames(video_id)
            if result['frames_added'] > 0:
                updated += 1
                details.append({
                    "video_id": video_id,
                    "filename": video['filename'],
                    "added_frames": result['frames_added']
                })
        except Exception as e:
            errors.append(f"Video {video_id}: {str(e)}")
            logger.error(f"Error filling missing frames for video {video_id}: {e}")
    
    return {
        "status": "success",
        "processed_videos": processed,
        "updated_videos": updated,
        "total_frames_added": sum(d['added_frames'] for d in details),
        "details": details,
        "errors": errors if errors else None
    }


@app.post("/api/videos/remove-duplicate-frames")
async def remove_duplicate_frames():
    """
    ONE-TIME MIGRATION: Remove duplicate frames from all videos.
    Keeps the frame with annotations if duplicates exist, otherwise keeps the first one.
    """
    videos = db.get_all_videos()
    total_removed = 0
    details = []
    
    for video in videos:
        video_id = video['id']
        
        # Get all frames for this video
        frames = db.get_frames_for_video(video_id)
        if not frames:
            continue
        
        # Group frames by frame_number
        from collections import defaultdict
        frame_groups = defaultdict(list)
        for frame in frames:
            frame_groups[frame['frame_number']].append(frame)
        
        # Find duplicates
        removed_count = 0
        for frame_number, frame_list in frame_groups.items():
            if len(frame_list) > 1:
                # Sort by: has annotations (desc), has review (desc), id (asc)
                # This keeps the annotated one, or reviewed one, or earliest one
                frame_list.sort(key=lambda f: (
                    -(f.get('annotation_count', 0) or 0),  # Prefer annotated
                    -(1 if f.get('reviewed') else 0),       # Prefer reviewed
                    f['id']                                  # Prefer older (lower id)
                ))
                
                # Keep the first one, delete the rest
                keep_frame = frame_list[0]
                for duplicate in frame_list[1:]:
                    try:
                        db.delete_frame(duplicate['id'])
                        removed_count += 1
                        logger.info(f"Deleted duplicate frame {duplicate['id']} (kept {keep_frame['id']}) for video {video_id}, frame_number {frame_number}")
                    except Exception as e:
                        logger.error(f"Error deleting duplicate frame {duplicate['id']}: {e}")
        
        if removed_count > 0:
            total_removed += removed_count
            details.append({
                "video_id": video_id,
                "filename": video['filename'],
                "removed_count": removed_count
            })
    
    return {
        "status": "success",
        "total_frames_removed": total_removed,
        "videos_affected": len(details),
        "details": details
    }


@app.post("/api/videos/clean-broken-frame-paths")
async def clean_broken_frame_paths():
    """
    ONE-TIME MIGRATION: Remove frames with broken /api/training-frames/ paths.
    """
    videos = db.get_all_videos()
    total_removed = 0
    details = []
    
    for video in videos:
        video_id = video['id']
        
        # Get all frames for this video
        frames = db.get_frames_for_video(video_id)
        if not frames:
            continue
        
        removed_count = 0
        for frame in frames:
            # Delete frames with broken /api/training-frames/ paths
            if frame.get('image_path', '').startswith('/api/training-frames/'):
                try:
                    db.delete_frame(frame['id'])
                    removed_count += 1
                    logger.info(f"Deleted frame {frame['id']} with broken path: {frame['image_path']}")
                except Exception as e:
                    logger.error(f"Error deleting frame {frame['id']}: {e}")
        
        if removed_count > 0:
            total_removed += removed_count
            details.append({
                "video_id": video_id,
                "filename": video['filename'],
                "removed_count": removed_count
            })
    
    return {
        "status": "success",
        "total_frames_removed": total_removed,
        "videos_affected": len(details),
        "details": details
    }


@app.post("/api/videos/merge-duplicate-frames")
async def merge_duplicate_frames():
    """
    Migration endpoint: Merge model detections from old frames into new frames with annotations.
    This handles the case where recovery created new frames while old frames with detections still existed.
    """
    videos = db.get_all_videos()
    total_merged = 0
    total_deleted = 0
    details = []
    
    for video in videos:
        video_id = video['id']
        filename = video['filename']
        
        # Get all frames for this video
        frames = db.get_frames_for_video(video_id)
        if not frames or len(frames) == 0:
            continue
        
        # Group frames by frame_number to find duplicates
        frame_groups = {}
        for frame in frames:
            frame_num = frame['frame_number']
            if frame_num not in frame_groups:
                frame_groups[frame_num] = []
            frame_groups[frame_num].append(frame)
        
        # Find frame numbers with duplicates
        duplicates = {fn: frames_list for fn, frames_list in frame_groups.items() if len(frames_list) > 1}
        
        if not duplicates:
            continue
        
        logger.info(f"Video {video_id} ({filename}): Found {len(duplicates)} frame numbers with duplicates")
        
        merged_count = 0
        deleted_count = 0
        
        for frame_num, duplicate_frames in duplicates.items():
            # Sort by ID - older frames first
            duplicate_frames.sort(key=lambda f: f['id'])
            
            # Find frame with annotations (newer frame) and frame with detections (older frame)
            frame_with_annotations = None
            frame_with_detections = None
            
            for frame in duplicate_frames:
                if frame.get('annotation_count', 0) > 0:
                    frame_with_annotations = frame
                if frame.get('detection_count', 0) > 0:
                    frame_with_detections = frame
            
            # If we have both, merge detections from old to new, then delete old
            if frame_with_annotations and frame_with_detections and frame_with_annotations['id'] != frame_with_detections['id']:
                # Copy detections from old frame to new frame
                conn = db.get_connection()
                cursor = conn.cursor()
                
                # Get detections from old frame
                cursor.execute("SELECT * FROM detections WHERE frame_id = ?", (frame_with_detections['id'],))
                old_detections = [dict(row) for row in cursor.fetchall()]
                
                # Copy to new frame
                for det in old_detections:
                    cursor.execute("""
                        INSERT INTO detections (frame_id, bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence, class_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (frame_with_annotations['id'], det['bbox_x1'], det['bbox_y1'], 
                          det['bbox_x2'], det['bbox_y2'], det['confidence'], det['class_name']))
                
                conn.commit()
                conn.close()
                
                merged_count += 1
                logger.info(f"  Merged {len(old_detections)} detections from frame {frame_with_detections['id']} to {frame_with_annotations['id']}")
                
                # Delete the old frame
                db.delete_frame(frame_with_detections['id'])
                deleted_count += 1
            
            # If we only have old frame with detections and new frame without, delete the new empty one
            elif frame_with_detections and not frame_with_annotations:
                # Keep the frame with detections, delete others
                for frame in duplicate_frames:
                    if frame['id'] != frame_with_detections['id']:
                        db.delete_frame(frame['id'])
                        deleted_count += 1
        
        if merged_count > 0 or deleted_count > 0:
            total_merged += merged_count
            total_deleted += deleted_count
            details.append({
                "video_id": video_id,
                "filename": filename,
                "duplicate_frame_numbers": len(duplicates),
                "frames_merged": merged_count,
                "frames_deleted": deleted_count
            })
            logger.info(f"  ✓ Video {video_id}: Merged {merged_count}, deleted {deleted_count} duplicate frames")
    
    return {
        "status": "success",
        "total_frames_merged": total_merged,
        "total_frames_deleted": total_deleted,
        "videos_affected": len(details),
        "details": details
    }


@app.post("/api/videos/recover-all-frames")
async def recover_all_video_frames():
    """
    Recovery endpoint: Re-analyze all videos that have no frames.
    Uses the same frame extraction and detection logic as video upload.
    """
    if not CV2_AVAILABLE:
        raise HTTPException(status_code=503, detail="OpenCV not available")
    
    det = load_detector()
    if not det:
        raise HTTPException(status_code=503, detail="Detector not initialized")
    
    # Get settings for sampling rate
    try:
        settings_data = db.get_settings()
        sample_rate_fps = settings_data.get('default_sampling_rate', 1.0)
    except (AttributeError, Exception):
        # Fallback if get_settings doesn't exist or fails
        sample_rate_fps = 1.0
        logger.info("Using default sampling rate of 1.0 fps")
    
    # Get all videos
    videos = db.get_all_videos()
    total_recovered = 0
    videos_processed = 0
    details = []
    
    import cv2
    frames_dir = Path("data/frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    
    for video in videos:
        video_id = video['id']
        video_path = video.get('video_path')
        filename = video['filename']
        
        # Skip if video has frames already
        existing_frames = db.get_frames_for_video(video_id)
        if existing_frames and len(existing_frames) > 0:
            logger.info(f"Video {video_id} ({filename}) already has {len(existing_frames)} frames, skipping")
            continue
        
        # Skip if video file doesn't exist
        if not video_path or not Path(video_path).exists():
            logger.warning(f"Video {video_id} ({filename}): File not found at {video_path}")
            continue
        
        logger.info(f"Recovering frames for video {video_id}: {filename}")
        
        # Open video
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.error(f"  Failed to open video file: {video_path}")
            continue
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Calculate frame interval based on sampling rate
        frame_interval = max(1, int(fps / sample_rate_fps)) if fps > 0 else 1
        
        frames_extracted = 0
        detections_found = 0
        frame_num = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Only process every Nth frame based on sample_rate
            if frame_num % frame_interval == 0:
                timestamp_in_video = frame_num / fps if fps > 0 else 0
                
                # Save frame to disk
                frame_filename = f"video_{video_id}_frame_{frame_num}.jpg"
                frame_path = frames_dir / frame_filename
                cv2.imwrite(str(frame_path), frame)
                
                # Run detection on this frame
                detections, annotated = det.detect(frame, return_annotated=True)
                
                # Save annotated version if there are detections
                if detections:
                    annotated_filename = f"video_{video_id}_frame_{frame_num}_annotated.jpg"
                    annotated_path = frames_dir / annotated_filename
                    cv2.imwrite(str(annotated_path), annotated)
                    detections_found += 1
                
                # Add frame to database
                frame_id = db.add_frame(
                    video_id=video_id,
                    frame_number=frame_num,
                    timestamp_in_video=timestamp_in_video,
                    image_path=f"data/frames/{frame_filename}",
                    has_detections=len(detections) > 0
                )
                
                # Add detections to database
                for detection in detections:
                    db.add_detection(
                        frame_id=frame_id,
                        bbox=detection['bbox'],
                        confidence=detection['confidence'],
                        class_name=detection.get('class_name', 'deer')
                    )
                
                frames_extracted += 1
            
            frame_num += 1
        
        cap.release()
        
        videos_processed += 1
        total_recovered += frames_extracted
        details.append({
            "video_id": video_id,
            "filename": filename,
            "frames_extracted": frames_extracted,
            "detections_found": detections_found,
            "sampling_rate_fps": sample_rate_fps,
            "frame_interval": frame_interval
        })
        
        logger.info(f"  ✓ Recovered {frames_extracted} frames ({detections_found} with detections)")
    
    return {
        "status": "success",
        "videos_processed": videos_processed,
        "total_frames_recovered": total_recovered,
        "sampling_rate_fps": sample_rate_fps,
        "details": details
    }


@app.post("/api/videos/sample-for-review")
async def sample_frames_for_review(video_ids: list[int] = None):
    """
    Sample representative frames from videos for early review.
    Selects 5 diverse frames per video using intelligent strategy.
    
    Args:
        video_ids: Optional list of video IDs. If None, samples from all videos.
    
    Returns:
        Statistics about sampled frames
    """
    # Get video IDs to sample from
    if video_ids is None:
        videos = db.get_all_videos()
        video_ids = [v['id'] for v in videos]
    
    if not video_ids:
        raise HTTPException(status_code=400, detail="No videos available to sample")
    
    total_sampled = 0
    frames_by_video = {}
    
    for video_id in video_ids:
        # Get all frames for this video
        frames = db.get_frames_for_video(video_id)
        
        if not frames:
            continue
        
        # Sample 5 representative frames
        sampled_frame_ids = _select_representative_frames(frames, count=5)
        
        # Mark them as selected for training
        for frame_id in sampled_frame_ids:
            db.mark_frame_for_training(frame_id)
        
        frames_by_video[video_id] = sampled_frame_ids
        total_sampled += len(sampled_frame_ids)
    
    return {
        "status": "success",
        "videos_sampled": len(frames_by_video),
        "total_frames_selected": total_sampled,
        "frames_per_video": frames_by_video
    }


def _select_representative_frames(frames: list, count: int = 5) -> list[int]:
    """
    Select representative frames from a video using intelligent sampling.
    
    Strategy:
    1. Highest confidence detection (if any)
    2. Medium confidence detection (0.4-0.7, if any)
    3. Random frame from first third (potential missed detections)
    4. Random frame from middle third
    5. Random frame from last third
    
    Falls back to even distribution if categories not available.
    """
    import random
    
    if len(frames) <= count:
        # If we have fewer frames than requested, return all
        return [f['id'] for f in frames]
    
    selected_ids = []
    remaining_frames = frames.copy()
    
    # 1. Highest confidence detection
    frames_with_detections = [f for f in remaining_frames if f.get('detection_count', 0) > 0]
    if frames_with_detections:
        # Get detections for each frame to find highest confidence
        max_conf_frame = max(frames_with_detections, key=lambda f: f.get('detection_count', 0))
        selected_ids.append(max_conf_frame['id'])
        remaining_frames.remove(max_conf_frame)
    
    # 2. Medium confidence - look for frames with 1-2 detections
    medium_frames = [f for f in remaining_frames if 1 <= f.get('detection_count', 0) <= 2]
    if medium_frames and len(selected_ids) < count:
        selected = random.choice(medium_frames)
        selected_ids.append(selected['id'])
        remaining_frames.remove(selected)
    
    # 3-5. Sample from temporal thirds
    if remaining_frames and len(selected_ids) < count:
        # Sort by frame number
        sorted_frames = sorted(remaining_frames, key=lambda f: f['frame_number'])
        third_size = len(sorted_frames) // 3
        
        # First third
        if third_size > 0 and len(selected_ids) < count:
            first_third = sorted_frames[:third_size]
            if first_third:
                selected = random.choice(first_third)
                selected_ids.append(selected['id'])
                sorted_frames.remove(selected)
        
        # Middle third
        if third_size > 0 and len(selected_ids) < count:
            middle_third = sorted_frames[third_size:2*third_size]
            if middle_third:
                selected = random.choice(middle_third)
                selected_ids.append(selected['id'])
                sorted_frames.remove(selected)
        
        # Last third
        if len(selected_ids) < count and sorted_frames:
            last_third = sorted_frames[2*third_size:]
            if last_third:
                selected = random.choice(last_third)
                selected_ids.append(selected['id'])
    
    # Fill remaining slots with random frames if needed
    if len(selected_ids) < count and remaining_frames:
        needed = count - len(selected_ids)
        available = [f for f in remaining_frames if f['id'] not in selected_ids]
        if available:
            additional = random.sample(available, min(needed, len(available)))
            selected_ids.extend([f['id'] for f in additional])
    
    return selected_ids


@app.get("/api/videos/training/status")
async def get_training_status():
    """Get status of training data collection."""
    stats = db.get_training_statistics()
    return {
        "video_count": stats['video_count'],
        "ready_for_review": stats['ready_for_review'],
        "ready_for_training": stats['ready_for_training'],
        "reviewed_frames": stats['reviewed_frames'],
        "annotation_count": stats['annotation_count']
    }


@app.post("/api/training/select-frames")
async def select_training_frames(target_count: int = 120):
    """
    Select diverse frames across all videos for training review.
    Uses smart algorithm to ensure diversity.
    """
    stats = db.get_training_statistics()
    
    # Run frame selection algorithm
    selected_frame_ids = db.select_diverse_frames(target_count)
    
    return {
        "status": "success",
        "frames_selected": len(selected_frame_ids),
        "frame_ids": selected_frame_ids
    }


@app.get("/api/training/frames")
async def get_selected_training_frames():
    """Get all frames selected for training review."""
    frames = db.get_training_frames()
    
    # Convert to format expected by frontend
    formatted_frames = []
    for frame in frames:
        # Build image URL
        image_url = f"/api/training-frames/{frame['image_path'].split('/')[-1]}" if frame.get('image_path') else None
        
        formatted_frame = {
            "id": frame['id'],
            "frame_number": frame['frame_number'],
            "video_id": frame['video_id'],
            "video_filename": frame['filename'],
            "timestamp_in_video": frame['timestamp_in_video'],
            "camera_name": frame.get('camera_name', 'Unknown'),
            "detection_count": len(frame['detections']),
            "annotation_count": len(frame['annotations']),
            "max_confidence": max([d['confidence'] for d in frame['detections']]) if frame['detections'] else 0.0,
            "image_path": frame['image_path'],
            "image_url": image_url,
            "reviewed": frame.get('reviewed', 0) == 1,
            "review_type": frame.get('review_type'),
            "detections": [
                {
                    'bbox': {
                        'x1': d['bbox_x1'],
                        'y1': d['bbox_y1'],
                        'x2': d['bbox_x2'],
                        'y2': d['bbox_y2']
                    },
                    'confidence': d['confidence'],
                    'class_name': d['class_name']
                }
                for d in frame['detections']
            ],
            "annotations": [
                {
                    'x': a['bbox_x'],
                    'y': a['bbox_y'],
                    'width': a['bbox_width'],
                    'height': a['bbox_height']
                }
                for a in frame['annotations']
            ]
        }
        formatted_frames.append(formatted_frame)
    
    return formatted_frames


@app.get("/api/training/stats/legacy")
async def get_training_stats_legacy():
    """Get training and review statistics (legacy in-memory version)."""
    # Count reviewed detections by type
    review_counts = {
        'correct': 0,
        'false_positive': 0,
        'incorrect_count': 0,
        'missed_deer': 0
    }
    
    for review in detection_reviews.values():
        review_type = review.get('review_type', 'correct')
        if review_type in review_counts:
            review_counts[review_type] += 1
    
    return {
        "total_detections": len(detection_history),
        "reviewed_detections": len(detection_reviews),
        "review_breakdown": review_counts,
        "missed_reports": len(missed_detections),
        "ready_for_training": len(detection_reviews) >= 50  # Minimum threshold
    }


@app.get("/api/training/preview-export")
async def preview_export():
    """
    Preview what would be exported without actually exporting.
    
    Returns statistics about training frames and annotations that would be exported.
    Use this to verify data before running the actual export.
    """
    try:
        # Get all training frames with their detections and annotations
        training_frames = db.get_training_frames()
        
        if not training_frames:
            return {
                "status": "no_data",
                "message": "No training frames found",
                "images_count": 0,
                "annotations_count": 0
            }
        
        # Count annotations
        total_model_detections = 0
        total_manual_annotations = 0
        videos_included = set()
        
        for frame in training_frames:
            total_model_detections += len(frame.get('detections', []))
            total_manual_annotations += len(frame.get('annotations', []))
            videos_included.add(frame.get('filename', 'unknown'))
        
        return {
            "status": "ready",
            "message": "Training data is ready to export",
            "statistics": {
                "total_frames": len(training_frames),
                "model_detections": total_model_detections,
                "manual_annotations": total_manual_annotations,
                "total_annotations": total_model_detections + total_manual_annotations,
                "videos_included": list(videos_included),
                "video_count": len(videos_included)
            },
            "safety": {
                "database_modified": False,
                "files_deleted": False,
                "creates_new_export_folder": True,
                "copies_images": True,
                "original_data_safe": True
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to preview export: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to preview export: {str(e)}"
        )


@app.post("/api/training/export-annotations")
async def export_training_annotations():
    """
    Export annotated training frames to COCO format for model training.
    
    This exports frames marked for training (selected_for_training=1) from the database,
    including both model detections and manual annotations.
    
    SAFETY: 
    - Creates automatic database backup before export
    - Only READS from the database and COPIES images
    - Original data is never modified or deleted
    """
    try:
        from datetime import datetime
        import shutil
        from PIL import Image
        
        # Automatic database backup (safety first!)
        db_path = Path("data/training.db")
        if db_path.exists():
            backup_dir = Path("data/backups")
            backup_dir.mkdir(exist_ok=True)
            timestamp_backup = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"training_backup_{timestamp_backup}.db"
            shutil.copy2(db_path, backup_path)
            logger.info(f"✓ Database backed up to {backup_path}")
        
        # Get all training frames with their detections and annotations
        training_frames = db.get_training_frames()
        
        if not training_frames:
            raise HTTPException(
                status_code=404,
                detail="No training frames found. Please annotate some videos first."
            )
        
        # Create export directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = Path(project_root) / "temp" / "training_export" / f"export_{timestamp}"
        images_dir = export_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)
        
        # Build COCO format dataset
        coco_data = {
            "info": {
                "description": "Deer Detection Training Dataset - Annotated Frames",
                "version": "1.0",
                "date_created": datetime.now().isoformat(),
                "contributor": "Deer Deterrent System"
            },
            "licenses": [],
            "categories": [
                {
                    "id": 1,
                    "name": "deer",
                    "supercategory": "animal"
                }
            ],
            "images": [],
            "annotations": []
        }
        
        annotation_id = 1
        images_copied = 0
        
        # Process each frame
        for frame in training_frames:
            # Copy image to export directory
            source_image = Path(frame['image_path'])
            if not source_image.exists():
                logger.warning(f"Image not found: {source_image}")
                continue
            
            # Use frame ID in filename to ensure uniqueness
            image_filename = f"frame_{frame['id']:06d}.jpg"
            dest_image = images_dir / image_filename
            shutil.copy2(source_image, dest_image)
            images_copied += 1
            
            # Get image dimensions
            img = Image.open(source_image)
            width, height = img.size
            
            # Add image to COCO
            image_entry = {
                "id": frame['id'],
                "file_name": image_filename,
                "width": width,
                "height": height,
                "video_filename": frame.get('filename', 'unknown'),
                "camera_name": frame.get('camera_name', 'unknown'),
                "frame_number": frame.get('frame_number', 0),
                "timestamp": frame.get('timestamp_in_video', 0.0)
            }
            coco_data["images"].append(image_entry)
            
            # Add model detections (confirmed by user viewing the frame)
            for detection in frame.get('detections', []):
                # Convert from pixel or normalized coordinates to COCO format
                x1 = detection['bbox_x1']
                y1 = detection['bbox_y1']
                x2 = detection['bbox_x2']
                y2 = detection['bbox_y2']
                
                # Handle normalized coordinates (0-1)
                if x1 <= 1.0 and y1 <= 1.0 and x2 <= 1.0 and y2 <= 1.0:
                    x1 = x1 * width
                    y1 = y1 * height
                    x2 = x2 * width
                    y2 = y2 * height
                
                bbox_width = x2 - x1
                bbox_height = y2 - y1
                
                annotation_entry = {
                    "id": annotation_id,
                    "image_id": frame['id'],
                    "category_id": 1,  # deer
                    "bbox": [x1, y1, bbox_width, bbox_height],
                    "area": bbox_width * bbox_height,
                    "iscrowd": 0,
                    "source": "model_detection",
                    "confidence": detection.get('confidence', 1.0)
                }
                coco_data["annotations"].append(annotation_entry)
                annotation_id += 1
            
            # Add manual annotations
            for annotation in frame.get('annotations', []):
                # Convert from normalized YOLO format (center x, center y, width, height)
                # to COCO format (top-left x, top-left y, width, height)
                x_center = annotation['bbox_x']
                y_center = annotation['bbox_y']
                bbox_width_norm = annotation['bbox_width']
                bbox_height_norm = annotation['bbox_height']
                
                # Convert to pixel coordinates
                x_center_px = x_center * width
                y_center_px = y_center * height
                bbox_width_px = bbox_width_norm * width
                bbox_height_px = bbox_height_norm * height
                
                # Convert center format to top-left corner format
                x1 = x_center_px - (bbox_width_px / 2)
                y1 = y_center_px - (bbox_height_px / 2)
                
                annotation_entry = {
                    "id": annotation_id,
                    "image_id": frame['id'],
                    "category_id": 1,  # deer
                    "bbox": [x1, y1, bbox_width_px, bbox_height_px],
                    "area": bbox_width_px * bbox_height_px,
                    "iscrowd": 0,
                    "source": "manual_annotation",
                    "annotator": annotation.get('annotator', 'user')
                }
                coco_data["annotations"].append(annotation_entry)
                annotation_id += 1
        
        # Save COCO JSON
        coco_json_path = export_dir / "annotations.json"
        with open(coco_json_path, 'w') as f:
            json.dump(coco_data, f, indent=2)
        
        logger.info(f"✓ Exported {len(coco_data['images'])} images with {len(coco_data['annotations'])} annotations to {export_dir}")
        
        return {
            "status": "success",
            "export_path": str(export_dir),
            "images_count": len(coco_data['images']),
            "images_copied": images_copied,
            "annotations_count": len(coco_data['annotations']),
            "timestamp": timestamp,
            "coco_json": str(coco_json_path)
        }
        
    except Exception as e:
        logger.error(f"Failed to export annotations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export annotations: {str(e)}"
        )


@app.get("/api/training/export")
async def export_training_data():
    """
    Export reviewed detections in COCO format for training.
    Includes both automatic detections and manual annotations.
    """
    from datetime import datetime
    import json
    from pathlib import Path
    
    # Create export directory
    export_dir = Path("temp/training_export")
    export_dir.mkdir(parents=True, exist_ok=True)
    
    # Collect all reviewed detections and detections with manual annotations
    export_detections = []
    
    # 1. Get reviewed detections from detection_reviews
    for det_id in detection_reviews:
        review = detection_reviews[det_id]
        if review["review_type"] in ["correct", "incorrect_count"]:
            # Find the full detection
            detection = None
            for d in detection_history:
                if d.get("id") == det_id:
                    detection = d
                    break
            if detection:
                export_detections.append({
                    "detection": detection,
                    "review": review,
                    "source": "reviewed"
                })
    
    # 2. Get detections with manual annotations (even if not formally reviewed)
    for detection in detection_history:
        if detection.get("manual_annotations") and len(detection["manual_annotations"]) > 0:
            # Check if not already added
            if not any(d["detection"].get("id") == detection.get("id") for d in export_detections):
                export_detections.append({
                    "detection": detection,
                    "review": None,
                    "source": "manual_annotation"
                })
    
    if not export_detections:
        raise HTTPException(status_code=404, detail="No training data to export (no reviews or annotations)")
    
    # Build COCO format dataset
    images = []
    annotations = []
    annotation_id = 1
    
    for i, item in enumerate(export_detections):
        detection = item["detection"]
        review = item["review"]
        
        # Image entry
        image_entry = {
            "id": i + 1,
            "file_name": Path(detection["image_path"]).name if detection.get("image_path") else f"detection_{i}.jpg",
            "width": 1920,  # Default - should be read from image if available
            "height": 1080,
            "date_captured": detection["timestamp"]
        }
        images.append(image_entry)
        
        # Add annotations
        # Priority: manual_annotations > automatic detections
        if detection.get("manual_annotations") and len(detection["manual_annotations"]) > 0:
            # Use manual bounding boxes
            for bbox in detection["manual_annotations"]:
                annotation = {
                    "id": annotation_id,
                    "image_id": i + 1,
                    "category_id": 1,  # Deer category
                    "bbox": [bbox["x"], bbox["y"], bbox["width"], bbox["height"]],  # COCO format: [x, y, width, height]
                    "area": bbox["width"] * bbox["height"],
                    "iscrowd": 0,
                    "source": "manual"
                }
                annotations.append(annotation)
                annotation_id += 1
        
        elif detection.get("detections") and len(detection["detections"]) > 0:
            # Use automatic detections if available
            for det in detection["detections"]:
                if "bbox" in det:
                    annotation = {
                        "id": annotation_id,
                        "image_id": i + 1,
                        "category_id": 1,
                        "bbox": det["bbox"],  # Already in COCO format from detector
                        "area": det["bbox"][2] * det["bbox"][3],
                        "iscrowd": 0,
                        "confidence": det.get("confidence", 0),
                        "source": "automatic"
                    }
                    annotations.append(annotation)
                    annotation_id += 1
        
        else:
            # Fallback: create annotation based on deer_count
            deer_count = review.get("corrected_deer_count") if review else detection.get("deer_count", 0)
            if deer_count > 0:
                # Create placeholder annotations (will need manual correction)
                for j in range(deer_count):
                    annotation = {
                        "id": annotation_id,
                        "image_id": i + 1,
                        "category_id": 1,
                        "bbox": [0, 0, 100, 100],  # Placeholder
                        "area": 10000,
                        "iscrowd": 0,
                        "source": "placeholder"
                    }
                    annotations.append(annotation)
                    annotation_id += 1
    
    # COCO dataset structure
    coco_data = {
        "info": {
            "description": "Deer Deterrent Training Dataset",
            "version": "1.0",
            "year": datetime.now().year,
            "date_created": datetime.now().isoformat(),
            "contributor": "Deer Deterrent System"
        },
        "licenses": [],
        "categories": [
            {
                "id": 1,
                "name": "deer",
                "supercategory": "animal"
            }
        ],
        "images": images,
        "annotations": annotations
    }
    
    # Save to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    export_path = export_dir / f"annotations_{timestamp}.json"
    with open(export_path, 'w') as f:
        json.dump(coco_data, f, indent=2)
    
    return {
        "status": "success",
        "export_path": str(export_path),
        "total_images": len(images),
        "total_annotations": len(annotations),
        "manual_annotations": sum(1 for a in annotations if a.get("source") == "manual"),
        "automatic_detections": sum(1 for a in annotations if a.get("source") == "automatic"),
        "reviewed_detections": sum(1 for item in export_detections if item["source"] == "reviewed"),
        "timestamp": timestamp
    }


@app.post("/api/training/sync-to-drive")
async def sync_training_to_drive():
    """Sync exported training data to Google Drive."""
    from pathlib import Path
    import os
    import sys
    
    # Add src to path
    sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
    
    try:
        from services.drive_sync import DriveSync
        from dotenv import load_dotenv
        load_dotenv()
        
        # Use environment variables with hardcoded defaults as fallback
        credentials_path = os.getenv(
            'GOOGLE_DRIVE_CREDENTIALS_PATH',
            'configs/google-credentials.json'
        )
        folder_id = os.getenv(
            'GOOGLE_DRIVE_TRAINING_FOLDER_ID',
            '1NUuOhA7rWCiGcxWPe6sOHNnzOKO0zZf5'
        )
        
        if not credentials_path or not folder_id:
            raise HTTPException(
                status_code=500,
                detail="Google Drive not configured. Set GOOGLE_DRIVE_CREDENTIALS_PATH and GOOGLE_DRIVE_TRAINING_FOLDER_ID in .env"
            )
        
        # Initialize Drive sync
        drive = DriveSync(credentials_path, folder_id)
        
        # Export training data first
        export_result = await export_training_data()
        export_dir = Path(export_result["export_path"]).parent
        
        # Sync to Drive
        version = datetime.now().strftime("production_%Y%m%d_%H%M%S")
        folder_id = drive.sync_training_dataset(export_dir, version)
        
        return {
            "status": "success",
            "message": "Training data synced to Google Drive",
            "version": version,
            "drive_folder_id": folder_id,
            **export_result
        }
        
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Google Drive dependencies not installed: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync to Drive: {e}"
        )


@app.post("/api/training/train-model")
async def train_model():
    """
    Complete training pipeline: Export annotations and sync to Google Drive.
    
    This endpoint:
    1. Creates automatic database backup
    2. Exports annotated frames to COCO format
    3. Syncs the export to Google Drive
    4. Returns information for running the Colab notebook
    """
    try:
        from pathlib import Path
        import os
        import shutil
        from datetime import datetime
        from dotenv import load_dotenv
        load_dotenv()
        
        # DEBUG: Log what we're seeing
        logger.info("=== TRAIN MODEL CALLED v2.0 ABSOLUTE PATHS ===")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Project root: {project_root}")
        
        # Step 0: Automatic database backup
        logger.info("Step 0: Creating database backup...")
        db_path = Path("data/training.db")
        if db_path.exists():
            backup_dir = Path("data/backups")
            backup_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"training_backup_{timestamp}.db"
            shutil.copy2(db_path, backup_path)
            logger.info(f"✓ Database backed up to {backup_path}")
        else:
            logger.warning("Database not found, skipping backup")
        
        # Step 1: Export annotations
        logger.info("Step 1: Exporting training annotations...")
        export_result = await export_training_annotations()
        
        if export_result["status"] != "success":
            raise HTTPException(
                status_code=500,
                detail="Failed to export annotations"
            )
        
        export_path = export_result["export_path"]
        logger.info(f"✓ Exported {export_result['images_count']} images with {export_result['annotations_count']} annotations")
        
        # Step 2: Sync to Google Drive
        logger.info("Step 2: Syncing to Google Drive...")
        
        # Use absolute paths
        credentials_path = '/home/rndpig/deer-deterrent/configs/google-credentials.json'
        folder_id = '1NUuOhA7rWCiGcxWPe6sOHNnzOKO0zZf5'
        
        logger.info(f"DEBUG: credentials_path = {credentials_path}")
        logger.info(f"DEBUG: folder_id = {folder_id}")
        logger.info(f"DEBUG: credentials_path exists = {Path(credentials_path).exists()}")
        
        if not credentials_path or not folder_id:
            raise HTTPException(
                status_code=500,
                detail=f"Google Drive not configured. credentials_path={credentials_path}, folder_id={folder_id}"
            )
        
        # Check if credentials file exists
        if not Path(credentials_path).exists():
            raise HTTPException(
                status_code=500,
                detail=f"Google Drive credentials file not found: {credentials_path}"
            )
        
        # Import and sync
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
        
        try:
            from services.drive_sync import DriveSync
            logger.info("✓ DriveSync imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import DriveSync: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Google Drive dependencies not installed. Run: pip install google-auth google-api-python-client"
            )
        
        try:
            drive = DriveSync(credentials_path, folder_id)
            logger.info("✓ DriveSync connected successfully")
        except FileNotFoundError as e:
            logger.error(f"Credentials file error: {e}")
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )
        except ConnectionError as e:
            logger.error(f"Google Drive connection error: {e}")
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"DriveSync initialization failed: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize Google Drive connection: {str(e)}"
            )
        
        # Step 2.1: Archive existing training data on Drive
        logger.info("Step 2.1: Archiving previous training data...")
        archive_folder_name = f"training_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Check if images and annotations.json exist at root
        existing_files = drive.service.files().list(
            q=f"'{folder_id}' in parents and trashed=false and (name='images' or name='annotations.json')",
            fields='files(id, name, mimeType)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute().get('files', [])
        
        if existing_files:
            # Create archive folder
            archive_folder_id = drive.create_folder(archive_folder_name, folder_id)
            logger.info(f"Created archive folder: {archive_folder_name}")
            
            # Move existing images folder and annotations.json to archive
            for file in existing_files:
                drive.service.files().update(
                    fileId=file['id'],
                    addParents=archive_folder_id,
                    removeParents=folder_id,
                    supportsAllDrives=True
                ).execute()
                logger.info(f"Moved {file['name']} to archive")
            
            logger.info(f"✓ Archived {len(existing_files)} items to {archive_folder_name}")
        else:
            logger.info("No existing training data to archive")
        
        # Step 2.2: Upload new training data to Drive
        logger.info("Step 2.2: Uploading new training data...")
        uploaded_files = drive.upload_directory(
            local_dir=Path(export_path),
            drive_folder_id=folder_id,
            exclude_patterns=['*.pyc', '__pycache__', '.git']
        )
        
        logger.info(f"✓ Synced {len(uploaded_files)} files to Google Drive")
        
        return {
            "status": "success",
            "message": "Training data exported and synced successfully",
            "export": {
                "images_count": export_result["images_count"],
                "annotations_count": export_result["annotations_count"],
                "local_path": export_path
            },
            "drive": {
                "folder_id": folder_id,
                "files_uploaded": len(uploaded_files)
            },
            "next_steps": {
                "instructions": "Open Google Colab notebook and run all cells",
                "notebook_url": "https://colab.research.google.com/drive/your-notebook-id",
                "drive_folder": f"https://drive.google.com/drive/folders/{folder_id}"
            }
        }
        
    except Exception as e:
        logger.error(f"Training pipeline failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Training pipeline failed: {str(e)}"
        )


@app.post("/api/training/deploy-latest")
async def deploy_latest_model():
    """
    Download latest trained model from Google Drive and deploy it
    """
    try:
        from services.drive_sync import DriveSync
        
        credentials_path = os.getenv(
            "GOOGLE_DRIVE_CREDENTIALS_PATH",
            "configs/google-credentials.json"
        )
        folder_id = os.getenv(
            "GOOGLE_DRIVE_TRAINING_FOLDER_ID",
            "1NUuOhA7rWCiGcxWPe6sOHNnzOKO0zZf5"
        )
        
        if not credentials_path or not folder_id:
            raise HTTPException(
                status_code=500,
                detail="Google Drive not configured"
            )
        
        # Initialize Drive sync
        drive = DriveSync(credentials_path, folder_id)
        
        # Download latest model
        model_info = drive.get_latest_model()
        
        if not model_info:
            raise HTTPException(
                status_code=404,
                detail="No trained models found in Google Drive"
            )
        
        # Model is now at model_info['local_path']
        local_model_path = model_info['local_path']
        
        # TODO: Validate model before deployment
        # - Check file size and format
        # - Run inference on test image
        # - Compare metrics with current model
        
        # Deploy to ml-detector service
        # For now, we'll move it to the models directory where detector can pick it up
        models_dir = Path(project_root) / "temp" / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        
        deployed_path = models_dir / f"deer_detection_latest.pt"
        shutil.copy2(local_model_path, deployed_path)
        
        return {
            "success": True,
            "message": "Model deployed successfully",
            "model_version": model_info['name'],
            "model_path": str(deployed_path),
            "modified_time": model_info['modified_time']
        }
        
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Google Drive dependencies not installed: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to deploy model: {e}"
        )


@app.post("/api/storage/r2-sync")
async def trigger_r2_sync(hours: int = 24, limit: int = 100):
    """
    Manually trigger R2 sync for recent snapshots.
    
    Args:
        hours: Sync snapshots from last N hours (default: 24)
        limit: Maximum snapshots to sync (default: 100)
    """
    r2 = load_r2_storage()
    if not r2:
        raise HTTPException(status_code=503, detail="R2 storage not configured")
    
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM ring_events 
            WHERE snapshot_path IS NOT NULL 
            AND timestamp > ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (cutoff, limit))
        
        snapshots = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not snapshots:
            return {
                "success": True,
                "message": "No snapshots to sync",
                "results": {"uploaded": 0, "failed": 0, "skipped": 0}
            }
        
        # Sync snapshots - snapshot_dir is /app in Docker
        snapshot_dir = Path("/app")
        results = r2.sync_snapshots_batch(snapshots, snapshot_dir)
        
        return {
            "success": True,
            "message": f"Synced {results['uploaded']} snapshots to R2",
            "results": results
        }
        
    except Exception as e:
        logger.error(f"R2 sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/storage/r2-status")
async def get_r2_status():
    """Check R2 storage configuration and connectivity."""
    r2 = load_r2_storage()
    
    if not r2:
        return {
            "configured": False,
            "message": "R2 credentials not set"
        }
    
    try:
        # Count all objects in bucket
        total_objects = 0
        paginator = r2.s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=r2.bucket_name):
            total_objects += page.get('KeyCount', 0)
        
        return {
            "configured": True,
            "connected": True,
            "bucket": r2.bucket_name,
            "objects_count": total_objects
        }
    except Exception as e:
        return {
            "configured": True,
            "connected": False,
            "error": str(e)
        }


@app.post("/api/storage/r2-clear")
async def clear_r2_bucket():
    """Clear all objects from R2 bucket."""
    r2 = load_r2_storage()
    
    if not r2:
        raise HTTPException(status_code=503, detail="R2 storage not configured")
    
    try:
        results = r2.clear_bucket()
        return {
            "success": True,
            "message": f"Cleared R2 bucket",
            "results": results
        }
    except Exception as e:
        logger.error(f"Failed to clear R2 bucket: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/storage/r2-sync-training")
async def sync_training_data_to_r2():
    """Sync all training-relevant data to R2."""
    from src.services.r2_sync import sync_training_data
    
    r2 = load_r2_storage()
    
    if not r2:
        raise HTTPException(status_code=503, detail="R2 storage not configured")
    
    try:
        base_dir = Path("/app")
        results = sync_training_data(db, r2, base_dir)
        
        return {
            "success": True,
            "message": "Training data sync complete",
            "results": results
        }
    except Exception as e:
        logger.error(f"Failed to sync training data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    print("Starting Deer Deterrent API server on http://localhost:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
