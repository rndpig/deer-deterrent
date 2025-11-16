"""
FastAPI backend for Deer Deterrent System.
Provides REST API and WebSocket for real-time updates.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, UploadFile, File
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
from collections import defaultdict
import tempfile
import shutil
import base64

# Add parent directory to path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)
print(f"Project root: {project_root}")

# Import database module
import database as db

# Lazy imports - only load when needed
detector = None

def load_detector():
    """Lazy load detector to avoid import errors if dependencies not installed."""
    global detector
    if detector is None:
        try:
            from src.inference.detector import DeerDetector
            # Try production model first, fall back to base model
            import os
            model_path = "models/deer_detector_best.pt" if os.path.exists("models/deer_detector_best.pt") else "models/yolov8n.pt"
            detector = DeerDetector(model_path=model_path, conf_threshold=settings.confidence_threshold)
            print(f"✓ Detector initialized with model: {model_path}")
        except Exception as e:
            print(f"⚠ Detector initialization failed: {e}")
            print("  Running in demo mode - detection features disabled")
    return detector

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
    description="Real-time deer detection and sprinkler control",
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
        "https://deer.rndpig.com",
        "https://deer-deterrent.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    sprinklers_activated: bool
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
    confidence_threshold: float = 0.6
    season_start: str = "04-01"
    season_end: str = "10-31"
    active_hours_enabled: bool = True
    active_hours_start: int = 20
    active_hours_end: int = 6
    sprinkler_duration: int = 30
    zone_cooldown: int = 300
    dry_run: bool = True

class ZoneConfig(BaseModel):
    name: str
    camera_id: str
    detection_area: Dict[str, float]
    sprinkler_zones: List[int]

# In-memory storage (will move to SQLite later)
settings = SystemSettings()
zones = []
stats = {
    "total_detections": 0,
    "total_deer": 0,
    "sprinklers_activated": 0,
    "last_detection": None
}


@app.on_event("startup")
async def startup_event():
    """Initialize detector on startup."""
    # Detector loaded lazily when first needed
    print("✓ Backend started - detector will load on first use")


@app.get("/")
async def root():
    """Health check."""
    return {
        "status": "ok",
        "name": "Deer Deterrent API",
        "version": "1.0.0",
        "detector_loaded": detector is not None
    }


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
                "sprinklers_activated": False,
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
    frames_dir = Path("data/training_frames")
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
            camera_name="Manual Upload",
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
                    "sprinklers_activated": False,
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
            "message": f"Video processed: {frames_extracted} frames extracted (every {sample_rate} frame{'s' if sample_rate > 1 else ''}), {detections_found} with detections"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")
    finally:
        await video.close()


@app.get("/api/training-frames/{frame_name}")
async def get_training_frame(frame_name: str):
    """Serve training frames."""
    frame_path = Path("data/training_frames") / frame_name
    if not frame_path.exists():
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
    if image_path.startswith('/api/training-frames/'):
        frame_filename = image_path.replace('/api/training-frames/', '')
        frame_path = Path("data/training_frames") / frame_filename
    else:
        raise HTTPException(status_code=404, detail="Frame path not found")
    
    if not frame_path.exists():
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
        db.mark_frame_for_training(frame_id, selected=True)
    
    return {"success": True, "frame_id": frame_id, "review_type": review_type}


@app.post("/api/frames/{frame_id}/annotate")
async def annotate_frame(frame_id: int, request: dict):
    """Add manual annotations to a frame."""
    annotations = request.get('annotations', [])
    
    # Get frame to ensure it exists
    frame = db.get_frame(frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame not found")
    
    # Save annotations
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
    stats["sprinklers_activated"] = 0
    
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
            "sprinklers_activated": not settings.dry_run
        })
        
        stats["total_detections"] += 1
        stats["total_deer"] += deer_count
        if not settings.dry_run:
            stats["sprinklers_activated"] += 1
    
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
    stats["sprinklers_activated"] = 0
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
    
    if stats['video_count'] < 10:
        raise HTTPException(
            status_code=400, 
            detail=f"Need at least 10 videos. Currently have {stats['video_count']}"
        )
    
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
                    'bbox_x': d['bbox_x1'],
                    'bbox_y': d['bbox_y1'],
                    'bbox_width': d['bbox_x2'] - d['bbox_x1'],
                    'bbox_height': d['bbox_y2'] - d['bbox_y1'],
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
        
        credentials_path = os.getenv('GOOGLE_DRIVE_CREDENTIALS_PATH')
        folder_id = os.getenv('GOOGLE_DRIVE_TRAINING_FOLDER_ID')
        
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


@app.post("/api/training/deploy-latest")
async def deploy_latest_model():
    """
    Download latest trained model from Google Drive and deploy it
    """
    try:
        from services.drive_sync import DriveSync
        
        credentials_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS_PATH")
        folder_id = os.getenv("GOOGLE_DRIVE_TRAINING_FOLDER_ID")
        
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
        models_dir = PROJECT_ROOT / "temp" / "models"
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


if __name__ == "__main__":
    import uvicorn
    print("Starting Deer Deterrent API server on http://localhost:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
