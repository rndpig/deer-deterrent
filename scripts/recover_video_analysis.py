#!/usr/bin/env python3
"""
Recovery script to re-analyze all videos and extract frames with detections.
This will rebuild the frames table for videos that lost their frame data.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, '/app')

import cv2
import numpy as np
from pathlib import Path
import database as db
from src.inference.detector import DeerDetector
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def recover_video_analysis():
    """Re-analyze all videos and extract frames."""
    
    # Initialize detector
    logger.info("Initializing detector...")
    detector = DeerDetector(
        model_path="yolov8n.pt",
        conf_threshold=0.25
    )
    
    # Get all videos
    videos = db.get_all_videos()
    logger.info(f"Found {len(videos)} videos to process")
    
    frames_dir = Path("data/training_frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    
    for video in videos:
        video_id = video['id']
        video_path = video.get('video_path')
        filename = video['filename']
        
        if not video_path or not Path(video_path).exists():
            logger.warning(f"Video {video_id} ({filename}): File not found at {video_path}")
            continue
            
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing video {video_id}: {filename}")
        logger.info(f"Path: {video_path}")
        
        # Check if video already has frames
        existing_frames = db.get_video_frames(video_id)
        if existing_frames and len(existing_frames) > 0:
            logger.info(f"  ✓ Video already has {len(existing_frames)} frames, skipping")
            continue
        
        # Open video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"  ✗ Failed to open video file")
            continue
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        logger.info(f"  Video info: {total_frames} frames @ {fps:.2f} fps ({duration:.2f}s)")
        
        # Get sampling rate from settings (default 1.0 fps)
        try:
            settings = db.get_settings()
            target_sampling_rate = settings.get('default_sampling_rate', 1.0)
        except:
            target_sampling_rate = 1.0  # Default if settings not available
            
        logger.info(f"  Using sampling rate: {target_sampling_rate} frames/sec")
        frame_interval = max(1, int(fps / target_sampling_rate))
        
        frames_extracted = 0
        frames_with_detections = 0
        frame_number = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            # Only process every Nth frame
            if frame_number % frame_interval == 0:
                timestamp = frame_number / fps if fps > 0 else 0
                
                # Run detection
                detections = detector.detect(frame)
                has_detections = len(detections) > 0
                
                if has_detections:
                    frames_with_detections += 1
                
                # Save frame image
                frame_filename = f"video_{video_id}_frame_{frame_number}.jpg"
                frame_path = frames_dir / frame_filename
                cv2.imwrite(str(frame_path), frame)
                
                # Store in database
                frame_id = db.add_frame(
                    video_id=video_id,
                    frame_number=frame_number,
                    timestamp=timestamp,
                    image_path=f"data/training_frames/{frame_filename}",
                    has_detections=has_detections
                )
                
                # Store detections
                if has_detections:
                    for det in detections:
                        db.add_detection(
                            frame_id=frame_id,
                            bbox=det['bbox'],
                            confidence=det['confidence'],
                            class_name=det['class']
                        )
                
                frames_extracted += 1
                
                if frames_extracted % 10 == 0:
                    logger.info(f"  Processed {frames_extracted} frames ({frames_with_detections} with detections)...")
            
            frame_number += 1
        
        cap.release()
        
        logger.info(f"  ✓ Complete: {frames_extracted} frames extracted, {frames_with_detections} with detections")

    logger.info(f"\n{'='*60}")
    logger.info("Recovery complete!")
    
    # Print summary
    videos = db.get_all_videos()
    total_frames = 0
    total_detections = 0
    
    for video in videos:
        frames = db.get_video_frames(video['id'])
        detections = sum(1 for f in frames if f.get('detection_count', 0) > 0)
        total_frames += len(frames)
        total_detections += detections
        
    logger.info(f"Database now has:")
    logger.info(f"  - {len(videos)} videos")
    logger.info(f"  - {total_frames} frames")
    logger.info(f"  - {total_detections} frames with detections")

if __name__ == "__main__":
    logger.info("Starting video recovery...")
    logger.info("This will re-analyze all videos and extract frames with detections")
    
    try:
        recover_video_analysis()
    except KeyboardInterrupt:
        logger.info("\nRecovery interrupted by user")
    except Exception as e:
        logger.error(f"Recovery failed: {e}", exc_info=True)
        sys.exit(1)
