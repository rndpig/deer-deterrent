#!/usr/bin/env python3
"""
ML Detector Service - YOLO26s Inference API
Provides REST API for deer detection using YOLO26s model with CLAHE preprocessing
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any
import io
import asyncio
import aiohttp

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from ultralytics import YOLO
from PIL import Image
import numpy as np
import cv2

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/ml_detector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Deer Detector ML Service",
    description="YOLO26s deer detection inference API with CLAHE preprocessing",
    version="1.0.0"
)

# Global model variable
model = None
MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "/app/models/production/best.pt")
MODEL_VERSION = "unknown"  # Loaded dynamically from VERSION file
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))
IOU_THRESHOLD = float(os.getenv("IOU_THRESHOLD", "0.65"))
DEVICE = os.getenv("DEVICE", "cpu")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://backend:8000")

# CLAHE preprocessing parameters — must match training export settings
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_SIZE = (8, 8)
ENABLE_CLAHE = os.getenv("ENABLE_CLAHE", "true").lower() == "true"

# API key for service-to-service auth
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")

# Settings refresh task
settings_refresh_task = None


async def fetch_settings_from_backend():
    """Fetch confidence threshold from backend API"""
    global CONFIDENCE_THRESHOLD
    try:
        headers = {}
        if INTERNAL_API_KEY:
            headers["X-API-Key"] = INTERNAL_API_KEY
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BACKEND_API_URL}/api/settings",
                headers=headers,
                timeout=5
            ) as response:
                if response.status == 200:
                    settings = await response.json()
                    new_threshold = settings.get('confidence_threshold')
                    if new_threshold is not None and new_threshold != CONFIDENCE_THRESHOLD:
                        old_threshold = CONFIDENCE_THRESHOLD
                        CONFIDENCE_THRESHOLD = float(new_threshold)
                        logger.info(f"Updated confidence threshold from {old_threshold} to {CONFIDENCE_THRESHOLD}")
                    return True
    except asyncio.TimeoutError:
        logger.warning("Timeout fetching settings from backend")
    except Exception as e:
        logger.warning(f"Could not fetch settings from backend: {e}")
    return False


async def settings_refresh_loop():
    """Background task to periodically refresh settings from backend"""
    logger.info("Starting settings refresh loop")
    # Initial fetch
    await fetch_settings_from_backend()
    
    # Refresh every 30 seconds
    while True:
        await asyncio.sleep(30)
        await fetch_settings_from_backend()


def load_model_version():
    """Load model version from VERSION file alongside the model"""
    global MODEL_VERSION
    version_path = Path(MODEL_PATH).parent / "VERSION"
    try:
        if version_path.exists():
            MODEL_VERSION = version_path.read_text().strip()
            logger.info(f"Loaded model version: {MODEL_VERSION}")
        else:
            MODEL_VERSION = "unknown"
            logger.warning(f"VERSION file not found at {version_path}, using 'unknown'")
    except Exception as e:
        MODEL_VERSION = "unknown"
        logger.warning(f"Could not read VERSION file: {e}")


def load_model():
    """Load YOLO model at startup"""
    global model
    try:
        logger.info(f"Loading YOLO model from {MODEL_PATH}")
        model = YOLO(MODEL_PATH)
        model.to(DEVICE)
        logger.info(f"Model loaded successfully on device: {DEVICE}")
        
        # Load model version from VERSION file
        load_model_version()
        
        # Warm up the model with a dummy inference
        dummy_image = np.zeros((640, 640, 3), dtype=np.uint8)
        _ = model(dummy_image, verbose=False)
        logger.info("Model warm-up complete")
        
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise


@app.on_event("startup")
async def startup_event():
    """Initialize model on startup"""
    global settings_refresh_task
    load_model()
    # Start background task to fetch settings from backend
    settings_refresh_task = asyncio.create_task(settings_refresh_loop())


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if settings_refresh_task:
        settings_refresh_task.cancel()


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Deer Detector ML Service",
        "status": "running",
        "model": MODEL_PATH,
        "device": DEVICE
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "model_path": MODEL_PATH,
        "model_version": MODEL_VERSION,
        "device": DEVICE,
        "confidence_threshold": CONFIDENCE_THRESHOLD
    }


@app.post("/detect")
async def detect_deer(file: UploadFile = File(...)) -> Dict[str, Any]:
    """
    Detect deer in uploaded image
    
    Args:
        file: Uploaded image file (JPEG, PNG)
    
    Returns:
        Detection results with bounding boxes and confidence scores
    """
    try:
        # Read image
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert to numpy array
        image_np = np.array(image)
        
        # Apply CLAHE preprocessing to match training data
        if ENABLE_CLAHE:
            try:
                lab = cv2.cvtColor(image_np, cv2.COLOR_RGB2LAB)
                l_channel, a_channel, b_channel = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_SIZE)
                enhanced_l = clahe.apply(l_channel)
                enhanced_lab = cv2.merge([enhanced_l, a_channel, b_channel])
                image_np = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2RGB)
            except Exception as e:
                logger.warning(f"CLAHE preprocessing failed, using original: {e}")
        
        logger.info(f"Processing image: {image.size}, mode: {image.mode}, clahe={ENABLE_CLAHE}")
        
        # Run inference
        results = model(
            image_np,
            conf=CONFIDENCE_THRESHOLD,
            iou=IOU_THRESHOLD,
            verbose=False
        )
        
        # Parse results
        detections = []
        deer_detected = False
        
        for result in results:
            boxes = result.boxes
            
            for box in boxes:
                class_id = int(box.cls[0])
                class_name = model.names[class_id]
                confidence = float(box.conf[0])
                bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                
                detection = {
                    "class": class_name,
                    "class_id": class_id,
                    "confidence": round(confidence, 4),
                    "bbox": {
                        "x1": round(bbox[0], 2),
                        "y1": round(bbox[1], 2),
                        "x2": round(bbox[2], 2),
                        "y2": round(bbox[3], 2)
                    }
                }
                
                detections.append(detection)
                
                # Check if deer detected
                # Only mark as deer_detected if the class is actually "deer"
                # The production model (best.pt) is trained specifically to detect deer
                if class_name.lower() == 'deer':
                    deer_detected = True
                    logger.info(f"Detected {class_name} with confidence {confidence:.2f}")
                else:
                    logger.info(f"Detected {class_name} with confidence {confidence:.2f} (not marked as deer)")
        
        response = {
            "deer_detected": deer_detected,
            "num_detections": len(detections),
            "detections": detections,
            "image_size": {
                "width": image.width,
                "height": image.height
            },
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "model_version": MODEL_VERSION
        }
        
        logger.info(f"Detection complete: {len(detections)} objects found, deer={deer_detected}")
        
        return response
    
    except Exception as e:
        logger.error(f"Detection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@app.post("/detect-batch")
async def detect_deer_batch(files: List[UploadFile] = File(...)) -> Dict[str, Any]:
    """
    Batch detection for multiple images
    
    Args:
        files: List of uploaded image files
    
    Returns:
        Batch detection results
    """
    results = []
    
    for file in files:
        try:
            result = await detect_deer(file)
            results.append({
                "filename": file.filename,
                "success": True,
                "result": result
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
    
    deer_count = sum(1 for r in results if r.get("success") and r["result"]["deer_detected"])
    
    return {
        "total_images": len(files),
        "successful": sum(1 for r in results if r.get("success")),
        "deer_detected_count": deer_count,
        "results": results
    }


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
