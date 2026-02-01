#!/usr/bin/env python3
"""
Comprehensive dataset query for v1.0 baseline
Includes: Ring snapshots + Video frames with annotations
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime
import json

def main():
    db_path = "/home/rndpig/deer-deterrent/backend/data/training.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=" * 80)
    print("DEER DETERRENT - TRAINING DATASET INVENTORY")
    print("=" * 80)
    
    # === PART 1: Ring Snapshots (Recent Detections) ===
    print("\n### PART 1: RING SNAPSHOTS (Live Detections)")
    print("-" * 80)
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total,
            MIN(timestamp) as earliest,
            MAX(timestamp) as latest
        FROM ring_events 
        WHERE deer_detected = 1 
        AND snapshot_available = 1
    """)
    
    row = cursor.fetchone()
    print(f"Total snapshots: {row['total']}")
    print(f"Date range: {row['earliest']} to {row['latest']}")
    
    # Check files
    snapshot_dir = Path("/home/rndpig/deer-deterrent/backend/data/snapshots")
    cursor.execute("""
        SELECT id, snapshot_path, detection_confidence
        FROM ring_events 
        WHERE deer_detected = 1 
        AND snapshot_available = 1
    """)
    
    snapshots_valid = 0
    snapshots_missing = []
    
    for row in cursor.fetchall():
        path = snapshot_dir / Path(row['snapshot_path']).name
        if path.exists():
            snapshots_valid += 1
        else:
            snapshots_missing.append(row['id'])
    
    print(f"Files exist: {snapshots_valid}")
    print(f"Files missing: {len(snapshots_missing)}")
    if snapshots_missing:
        print(f"  Missing event IDs: {snapshots_missing}")
    
    # === PART 2: Video Archive (Manually Uploaded) ===
    print("\n### PART 2: VIDEO ARCHIVE (Manual Uploads)")
    print("-" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM videos")
    video_count = cursor.fetchone()[0]
    print(f"Total videos: {video_count}")
    
    # Check video files
    video_dir = Path("/home/rndpig/deer-deterrent/backend/data/video_archive")
    video_files = list(video_dir.glob("*.mp4")) + list(video_dir.glob("*.mov")) + list(video_dir.glob("*.MP4"))
    print(f"Video files on disk: {len(video_files)}")
    
    # Calculate total size
    total_size_mb = sum(f.stat().st_size for f in video_files) / (1024 * 1024)
    print(f"Total video size: {total_size_mb:.1f} MB")
    
    # === PART 3: Extracted Frames ===
    print("\n### PART 3: EXTRACTED FRAMES")
    print("-" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM frames")
    frames_in_db = cursor.fetchone()[0]
    print(f"Frames in database: {frames_in_db}")
    
    cursor.execute("SELECT COUNT(*) FROM frames WHERE selected_for_training = 1")
    frames_selected = cursor.fetchone()[0]
    print(f"Frames selected for training: {frames_selected}")
    
    cursor.execute("SELECT COUNT(*) FROM frames WHERE has_detections = 1")
    frames_with_deer = cursor.fetchone()[0]
    print(f"Frames with deer detections: {frames_with_deer}")
    
    # Check frame files
    frames_dir = Path("/home/rndpig/deer-deterrent/backend/data/frames")
    frame_files = list(frames_dir.glob("*.jpg"))
    annotated_files = [f for f in frame_files if "_annotated" in f.name]
    clean_files = [f for f in frame_files if "_annotated" not in f.name]
    
    print(f"\nFrame files on disk:")
    print(f"  Clean frames: {len(clean_files)}")
    print(f"  Annotated (visual): {len(annotated_files)}")
    print(f"  Total: {len(frame_files)}")
    
    # === PART 4: Annotations (Bounding Boxes) ===
    print("\n### PART 4: ANNOTATIONS (Bounding Boxes)")
    print("-" * 80)
    
    cursor.execute("SELECT COUNT(*) FROM annotations")
    annotation_count = cursor.fetchone()[0]
    print(f"Total annotations (user corrections): {annotation_count}")
    
    cursor.execute("SELECT COUNT(*) FROM detections")
    detection_count = cursor.fetchone()[0]
    print(f"Total detections (model predictions): {detection_count}")
    
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT frame_id) as frames_with_annotations
        FROM annotations
    """)
    frames_annotated = cursor.fetchone()[0]
    print(f"Frames with manual annotations: {frames_annotated}")
    
    # === PART 5: Training Data Summary ===
    print("\n### PART 5: TRAINING DATA SUMMARY")
    print("=" * 80)
    
    total_images = snapshots_valid + len(clean_files)
    total_labeled = frames_annotated  # Frames with bounding box labels
    
    print(f"Total usable images: {total_images}")
    print(f"  - Ring snapshots: {snapshots_valid}")
    print(f"  - Video frames: {len(clean_files)}")
    print(f"\nLabeled data (with bounding boxes): {total_labeled}")
    print(f"Unlabeled data: {total_images - total_labeled}")
    
    # Check for YOLO label files
    label_files = list(frames_dir.glob("*.txt"))
    print(f"\nYOLO format labels (.txt files): {len(label_files)}")
    
    if len(label_files) == 0:
        print("  ⚠️  No YOLO labels found - annotations need to be converted!")
    
    # === PART 6: Data Quality ===
    print("\n### PART 6: DATA QUALITY CHECKS")
    print("-" * 80)
    
    # Check for frames without annotations
    cursor.execute("""
        SELECT COUNT(*) 
        FROM frames 
        WHERE has_detections = 1 
        AND id NOT IN (SELECT frame_id FROM annotations)
        AND id NOT IN (SELECT frame_id FROM detections)
    """)
    frames_missing_labels = cursor.fetchone()[0]
    
    if frames_missing_labels > 0:
        print(f"⚠️  {frames_missing_labels} frames marked as having deer but no bbox labels!")
    else:
        print("✅ All frames with deer have bbox labels")
    
    # Check annotation distribution
    cursor.execute("""
        SELECT 
            annotation_type,
            COUNT(*) as count
        FROM annotations
        GROUP BY annotation_type
    """)
    
    print("\nAnnotation types:")
    for row in cursor.fetchall():
        print(f"  - {row['annotation_type']}: {row['count']}")
    
    # === SUMMARY FOR v1.0 DATASET ===
    print("\n" + "=" * 80)
    print("RECOMMENDATION FOR v1.0_BASELINE DATASET")
    print("=" * 80)
    
    print(f"""
Dataset Composition:
  1. Ring Snapshots: {snapshots_valid} images (recent detections, Jan 2026)
  2. Video Frames: {len(clean_files)} images (historical, Nov-Dec 2025)
  3. Total Images: {total_images}
  
Labeling Status:
  - Frames with bounding boxes: {total_labeled}
  - Needs YOLO label conversion: {total_labeled > 0 and len(label_files) == 0}
  
Next Steps:
  1. Export annotations from database → YOLO .txt format
  2. Combine Ring snapshots + video frames → v1.0_baseline/
  3. Generate train/val/test splits (80/10/10)
  4. Create manifest.csv with metadata
  5. Create data.yaml for YOLO training
    """)
    
    conn.close()

if __name__ == "__main__":
    main()
