#!/usr/bin/env python3
"""
Dataset Export Script - v1.0 Baseline
Exports annotated frames and snapshots from database to YOLO format

Handles:
1. Video frames with manual annotations
2. Ring snapshots with deer detections  
3. Converts bbox from database → YOLO format (.txt files)
4. Generates train/val/test splits
5. Creates manifest with metadata
"""

import sqlite3
import shutil
import json
import hashlib
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import random

# Configuration
DB_PATH = "/home/rndpig/deer-deterrent/backend/data/training.db"
SNAPSHOTS_DIR = Path("/home/rndpig/deer-deterrent/backend/data/snapshots")
FRAMES_DIR = Path("/home/rndpig/deer-deterrent/backend/data/frames")
OUTPUT_DIR = Path("/home/rndpig/deer-deterrent/data/training_datasets/v1.0_2026-01-baseline")

# Split ratios
TRAIN_RATIO = 0.8
VAL_RATIO = 0.1
TEST_RATIO = 0.1

# YOLO class mapping
CLASS_NAMES = ["deer"]  # Class 0 = deer

def get_image_hash(image_path: Path) -> str:
    """Calculate SHA256 hash of image file"""
    sha256 = hashlib.sha256()
    with open(image_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]  # First 16 chars

def bbox_to_yolo(bbox: Dict, img_width: int, img_height: int) -> str:
    """
    Convert database bbox to YOLO format
    Database: {x, y, width, height} (already normalized 0-1, top-left corner format)
    YOLO: <class> <x_center> <y_center> <width> <height> (normalized 0-1, center format)
    """
    # bbox is already normalized, just need to convert from corner to center format
    x_center = bbox['x'] + bbox['width'] / 2
    y_center = bbox['y'] + bbox['height'] / 2
    
    # Width and height are already normalized
    norm_width = bbox['width']
    norm_height = bbox['height']
    
    # YOLO format: class x_center y_center width height
    return f"0 {x_center:.6f} {y_center:.6f} {norm_width:.6f} {norm_height:.6f}"

def get_image_dimensions(image_path: Path) -> Tuple[int, int]:
    """Get image width and height"""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.size  # (width, height)
    except:
        # Fallback: assume standard Ring camera resolution
        return (1920, 1080)

def determine_season(timestamp_str: str) -> str:
    """Determine season from timestamp"""
    try:
        dt = datetime.fromisoformat(timestamp_str.replace('T', ' ').split('.')[0])
        month = dt.month
        
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:  # 9, 10, 11
            return "fall"
    except:
        return "unknown"

def export_dataset():
    """Main export function"""
    
    print("=" * 80)
    print("EXPORTING DATASET v1.0_2026-01-baseline")
    print("=" * 80)
    
    # Create output directory structure
    output_images = OUTPUT_DIR / "images"
    output_labels = OUTPUT_DIR / "labels"
    
    for split in ["train", "val", "test"]:
        (output_images / split).mkdir(parents=True, exist_ok=True)
        (output_labels / split).mkdir(parents=True, exist_ok=True)
    
    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # === PART 1: Export Video Frames with Annotations ===
    print("\n### PART 1: Exporting Video Frames with Annotations")
    print("-" * 80)
    
    # Get all frames with annotations
    cursor.execute("""
        SELECT DISTINCT
            f.id as frame_id,
            f.image_path,
            v.filename as video_name,
            v.camera_name,
            v.captured_at,
            f.frame_number
        FROM frames f
        JOIN videos v ON f.video_id = v.id
        WHERE f.id IN (SELECT DISTINCT frame_id FROM annotations)
        ORDER BY f.id
    """)
    
    frames_with_annotations = cursor.fetchall()
    print(f"Found {len(frames_with_annotations)} frames with annotations")
    
    manifest_data = []
    exported_count = 0
    
    for frame in frames_with_annotations:
        frame_id = frame['frame_id']
        source_path = FRAMES_DIR / Path(frame['image_path']).name
        
        # Skip if file doesn't exist
        if not source_path.exists():
            print(f"  ⚠️  Missing: {source_path.name}")
            continue
        
        # Get all annotations for this frame
        cursor.execute("""
            SELECT bbox_x, bbox_y, bbox_width, bbox_height
            FROM annotations
            WHERE frame_id = ?
        """, (frame_id,))
        
        annotations = cursor.fetchall()
        
        if len(annotations) == 0:
            continue
        
        # Get image dimensions
        img_width, img_height = get_image_dimensions(source_path)
        
        # Convert annotations to YOLO format
        yolo_lines = []
        for ann in annotations:
            bbox = {
                'x': ann['bbox_x'],
                'y': ann['bbox_y'],
                'width': ann['bbox_width'],
                'height': ann['bbox_height']
            }
            yolo_lines.append(bbox_to_yolo(bbox, img_width, img_height))
        
        # Generate unique filename
        file_hash = get_image_hash(source_path)
        new_filename = f"frame_{frame_id:06d}_{file_hash}.jpg"
        
        # Assign to split (stratified by video to avoid leakage)
        rand_val = random.random()
        if rand_val < TRAIN_RATIO:
            split = "train"
        elif rand_val < TRAIN_RATIO + VAL_RATIO:
            split = "val"
        else:
            split = "test"
        
        # Copy image
        dest_image = output_images / split / new_filename
        shutil.copy2(source_path, dest_image)
        
        # Write YOLO label file
        dest_label = output_labels / split / new_filename.replace('.jpg', '.txt')
        with open(dest_label, 'w') as f:
            f.write('\n'.join(yolo_lines))
        
        # Add to manifest
        manifest_data.append({
            'filename': new_filename,
            'split': split,
            'source_type': 'video_frame',
            'frame_id': frame_id,
            'video_name': frame['video_name'],
            'frame_number': frame['frame_number'],
            'camera_name': frame['camera_name'] or 'unknown',
            'captured_at': frame['captured_at'],
            'season': determine_season(frame['captured_at'] or ''),
            'num_annotations': len(annotations),
            'image_hash': file_hash,
            'resolution': f"{img_width}x{img_height}"
        })
        
        exported_count += 1
        if exported_count % 50 == 0:
            print(f"  Exported {exported_count}/{len(frames_with_annotations)} frames...")
    
    print(f"✅ Exported {exported_count} video frames")
    
    # === PART 2: Export Ring Snapshots ===
    print("\n### PART 2: Exporting Ring Snapshots with Deer")
    print("-" * 80)
    
    cursor.execute("""
        SELECT 
            id,
            camera_id,
            timestamp,
            snapshot_path,
            detection_confidence
        FROM ring_events
        WHERE deer_detected = 1
        AND snapshot_available = 1
    """)
    
    snapshots = cursor.fetchall()
    print(f"Found {len(snapshots)} Ring snapshots")
    
    snapshot_exported = 0
    
    for snapshot in snapshots:
        source_path = SNAPSHOTS_DIR / Path(snapshot['snapshot_path']).name
        
        if not source_path.exists():
            print(f"  ⚠️  Missing: {source_path.name}")
            continue
        
        # For Ring snapshots, we don't have bbox annotations yet
        # These are "weakly labeled" - we know deer are present but no precise bbox
        # Skip for now, or include as val/test only
        
        # Option: Include without labels for testing model's detection capability
        # For v1.0, we'll skip these and focus on fully annotated data
        # They can be added to v1.1 after manual annotation
        
    print(f"ℹ️  Skipping {len(snapshots)} Ring snapshots (no bbox annotations yet)")
    print(f"   These can be added to v1.1 after manual annotation")
    
    # === PART 3: Generate Manifest ===
    print("\n### PART 3: Generating Manifest")
    print("-" * 80)
    
    manifest_path = OUTPUT_DIR / "manifest.csv"
    
    with open(manifest_path, 'w', newline='') as f:
        if manifest_data:
            writer = csv.DictWriter(f, fieldnames=manifest_data[0].keys())
            writer.writeheader()
            writer.writerows(manifest_data)
    
    print(f"✅ Manifest saved: {manifest_path}")
    
    # === PART 4: Generate data.yaml ===
    print("\n### PART 4: Generating data.yaml")
    print("-" * 80)
    
    # Count files in each split
    train_count = len(list((output_images / "train").glob("*.jpg")))
    val_count = len(list((output_images / "val").glob("*.jpg")))
    test_count = len(list((output_images / "test").glob("*.jpg")))
    
    data_yaml = {
        'path': str(OUTPUT_DIR.absolute()),
        'train': 'images/train',
        'val': 'images/val',
        'test': 'images/test',
        'names': {
            0: 'deer'
        },
        'nc': 1,  # number of classes
        'notes': f'Dataset v1.0 - Exported {datetime.now().isoformat()}',
        'stats': {
            'train_images': train_count,
            'val_images': val_count,
            'test_images': test_count,
            'total_images': train_count + val_count + test_count
        }
    }
    
    yaml_path = OUTPUT_DIR / "data.yaml"
    with open(yaml_path, 'w') as f:
        # Write YAML manually for better formatting
        f.write(f"# Deer Deterrent Dataset v1.0 - Baseline\n")
        f.write(f"# Exported: {datetime.now().isoformat()}\n")
        f.write(f"# Source: Video frames with manual annotations\n\n")
        f.write(f"path: {data_yaml['path']}\n")
        f.write(f"train: {data_yaml['train']}\n")
        f.write(f"val: {data_yaml['val']}\n")
        f.write(f"test: {data_yaml['test']}\n\n")
        f.write(f"nc: {data_yaml['nc']}\n")
        f.write(f"names:\n")
        f.write(f"  0: deer\n\n")
        f.write(f"# Dataset Statistics\n")
        f.write(f"# Train: {train_count} images\n")
        f.write(f"# Val: {val_count} images\n")
        f.write(f"# Test: {test_count} images\n")
        f.write(f"# Total: {train_count + val_count + test_count} images\n")
    
    print(f"✅ data.yaml saved: {yaml_path}")
    
    # === PART 5: Generate metadata.json ===
    print("\n### PART 5: Generating metadata.json")
    print("-" * 80)
    
    metadata = {
        'version': '1.0',
        'name': 'v1.0_2026-01-baseline',
        'created_at': datetime.now().isoformat(),
        'description': 'Initial baseline dataset with manually annotated video frames',
        'source': {
            'video_frames': exported_count,
            'ring_snapshots': 0,
            'videos_processed': len(set(item['video_name'] for item in manifest_data))
        },
        'statistics': {
            'total_images': train_count + val_count + test_count,
            'train_images': train_count,
            'val_images': val_count,
            'test_images': test_count,
            'total_annotations': sum(item['num_annotations'] for item in manifest_data),
            'avg_annotations_per_image': sum(item['num_annotations'] for item in manifest_data) / len(manifest_data) if manifest_data else 0
        },
        'splits': {
            'train': f'{TRAIN_RATIO * 100:.0f}%',
            'val': f'{VAL_RATIO * 100:.0f}%',
            'test': f'{TEST_RATIO * 100:.0f}%'
        },
        'classes': CLASS_NAMES,
        'camera_info': {
            'cameras': list(set(item['camera_name'] for item in manifest_data)),
            'primary_camera': 'Side'
        },
        'temporal_coverage': {
            'earliest': min(item['captured_at'] for item in manifest_data if item['captured_at']),
            'latest': max(item['captured_at'] for item in manifest_data if item['captured_at']),
            'seasons': list(set(item['season'] for item in manifest_data))
        }
    }
    
    metadata_path = OUTPUT_DIR / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ metadata.json saved: {metadata_path}")
    
    # === SUMMARY ===
    print("\n" + "=" * 80)
    print("EXPORT COMPLETE!")
    print("=" * 80)
    print(f"\nDataset Location: {OUTPUT_DIR}")
    print(f"\nStatistics:")
    print(f"  Train: {train_count} images")
    print(f"  Val: {val_count} images")
    print(f"  Test: {test_count} images")
    print(f"  Total: {train_count + val_count + test_count} images")
    print(f"\nFiles Generated:")
    print(f"  ✓ images/ - Training images organized by split")
    print(f"  ✓ labels/ - YOLO format annotations (.txt)")
    print(f"  ✓ data.yaml - YOLO training configuration")
    print(f"  ✓ manifest.csv - Detailed metadata")
    print(f"  ✓ metadata.json - Dataset summary")
    print(f"\nNext Steps:")
    print(f"  1. Review dataset: ls -lh {OUTPUT_DIR}")
    print(f"  2. Train YOLO26: yolo detect train data={OUTPUT_DIR}/data.yaml model=yolo26n.pt")
    print(f"  3. Update model registry with results")
    
    conn.close()

if __name__ == "__main__":
    # Set random seed for reproducible splits
    random.seed(42)
    export_dataset()
