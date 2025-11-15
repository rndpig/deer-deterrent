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
detection_history = []
detection_reviews = {}  # Store manual reviews for training
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

class DetectionReview(BaseModel):
    detection_id: str
    review_type: str  # 'correct', 'false_positive', 'missed_deer', 'incorrect_count'
    corrected_deer_count: int = None
    notes: str = None
    reviewed_at: str = None
    reviewer: str = "admin"

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
    """Get detection history."""
    return detection_history[offset:offset + limit]


@app.get("/api/detections/recent")
async def get_recent_detections(hours: int = 24):
    """Get detections from last N hours."""
    cutoff = datetime.now() - timedelta(hours=hours)
    recent = [
        d for d in detection_history
        if datetime.fromisoformat(d["timestamp"]) > cutoff
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


@app.get("/api/training/export")
async def export_training_data():
    """Export reviewed detections in COCO format for training."""
    from datetime import datetime
    import json
    from pathlib import Path
    
    # Create export directory
    export_dir = Path("temp/training_export")
    export_dir.mkdir(parents=True, exist_ok=True)
    
    # Filter reviewed detections
    reviewed = [
        {**detection_reviews[det_id], "id": det_id}
        for det_id in detection_reviews
        if detection_reviews[det_id]["review_type"] in ["correct", "incorrect_count"]
    ]
    
    if not reviewed:
        raise HTTPException(status_code=404, detail="No reviewed detections to export")
    
    # Build COCO format dataset
    images = []
    annotations = []
    
    for i, review in enumerate(reviewed):
        detection = review["detection"]
        
        # Image entry
        image_entry = {
            "id": i + 1,
            "file_name": Path(detection["image_path"]).name if detection.get("image_path") else f"detection_{i}.jpg",
            "width": 1920,  # Adjust based on your camera resolution
            "height": 1080,
            "date_captured": detection["timestamp"]
        }
        images.append(image_entry)
        
        # Annotation entry (simplified - would need bounding boxes from actual detections)
        deer_count = review.get("corrected_deer_count") or detection["deer_count"]
        for j in range(deer_count):
            annotation = {
                "id": len(annotations) + 1,
                "image_id": i + 1,
                "category_id": 1,  # Deer category
                "bbox": [0, 0, 100, 100],  # Placeholder - needs actual bbox data
                "area": 10000,
                "iscrowd": 0
            }
            annotations.append(annotation)
    
    # COCO dataset structure
    coco_data = {
        "info": {
            "description": "Deer Deterrent Training Dataset",
            "version": "1.0",
            "year": datetime.now().year,
            "date_created": datetime.now().isoformat()
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
    export_path = export_dir / f"annotations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(export_path, 'w') as f:
        json.dump(coco_data, f, indent=2)
    
    return {
        "status": "success",
        "export_path": str(export_path),
        "images_count": len(images),
        "annotations_count": len(annotations),
        "reviewed_detections": len(reviewed)
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
