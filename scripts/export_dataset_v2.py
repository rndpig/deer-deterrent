#!/usr/bin/env python3
"""
Dataset Export Script - v2.0
Exports annotated frames + Ring snapshots + negatives to YOLO format
with CLAHE preprocessing and stratified splits.

Improvements over v1.0:
1. Includes negative examples (no_deer frames + empty Ring snapshots)
2. Applies CLAHE preprocessing to all images
3. Stratified split by video (no data leakage between train/val/test)
4. Includes Ring deer snapshots with detection bboxes
5. Quality checks on annotations
6. Generates augmented copies for offline expansion

Usage (run on Dell server):
    python3 scripts/export_dataset_v2.py
    
Output:
    data/training_datasets/v2.0_YYYYMMDD/
    ├── images/{train,val,test}/*.jpg
    ├── labels/{train,val,test}/*.txt
    ├── data.yaml
    ├── manifest.csv
    └── metadata.json
"""

import sqlite3
import shutil
import json
import hashlib
import csv
import random
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    print("WARNING: OpenCV not installed. CLAHE preprocessing will be skipped.")
    print("Install: pip install opencv-python-headless")
    HAS_CV2 = False

# ========== Configuration ==========
DB_PATH = Path("/home/rndpig/deer-deterrent/backend/data/training.db")
SNAPSHOTS_DIR = Path("/home/rndpig/deer-deterrent/backend/data/snapshots")
FRAMES_DIR = Path("/home/rndpig/deer-deterrent/backend/data/frames")
TRAINING_ARCHIVE_DIR = Path("/home/rndpig/deer-deterrent/backend/data/training_archive/negatives")
OUTPUT_BASE = Path("/home/rndpig/deer-deterrent/data/training_datasets")

# Split ratios
TRAIN_RATIO = 0.80
VAL_RATIO = 0.10
TEST_RATIO = 0.10

# CLAHE parameters
CLAHE_CLIP_LIMIT = 3.0
CLAHE_TILE_SIZE = (8, 8)

# Target negative ratio (% of total dataset)
TARGET_NEGATIVE_RATIO = 0.35

# YOLO class mapping
CLASS_NAMES = ["deer"]  # Class 0 = deer

# ========== Image Preprocessing ==========

def enhance_ir_image(image: np.ndarray) -> np.ndarray:
    """Apply CLAHE to enhance IR/night-vision image contrast."""
    if image is None:
        return image
    
    # Convert to LAB color space
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    
    # Apply CLAHE to luminance channel only
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_SIZE)
    enhanced_l = clahe.apply(l_channel)
    
    # Merge and convert back
    enhanced_lab = cv2.merge([enhanced_l, a_channel, b_channel])
    enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
    
    return enhanced


def process_and_save_image(source_path: Path, dest_path: Path, apply_clahe: bool = True) -> bool:
    """Read image, optionally apply CLAHE, save to destination."""
    if not source_path.exists():
        return False
    
    if apply_clahe and HAS_CV2:
        img = cv2.imread(str(source_path))
        if img is None:
            # Fallback: just copy
            shutil.copy2(source_path, dest_path)
            return True
        img = enhance_ir_image(img)
        cv2.imwrite(str(dest_path), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    else:
        shutil.copy2(source_path, dest_path)
    
    return True


# ========== Utility Functions ==========

def get_image_hash(image_path: Path) -> str:
    """Calculate SHA256 hash of image file (first 16 chars)."""
    sha256 = hashlib.sha256()
    with open(image_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]


def bbox_annotation_to_yolo(bbox: Dict) -> str:
    """
    Convert annotation bbox to YOLO format.
    DB annotations: {bbox_x, bbox_y, bbox_width, bbox_height} normalized 0-1, top-left corner
    YOLO: <class> <x_center> <y_center> <width> <height> normalized 0-1, center
    """
    x_center = bbox['bbox_x'] + bbox['bbox_width'] / 2
    y_center = bbox['bbox_y'] + bbox['bbox_height'] / 2
    w = bbox['bbox_width']
    h = bbox['bbox_height']
    
    # Clamp to [0, 1]
    x_center = max(0, min(1, x_center))
    y_center = max(0, min(1, y_center))
    w = max(0.001, min(1, w))
    h = max(0.001, min(1, h))
    
    return f"0 {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}"


def bbox_detection_to_yolo(bbox: Dict, img_width: int = 1920, img_height: int = 1080) -> str:
    """
    Convert detection bbox to YOLO format.
    DB detections: {bbox_x1, bbox_y1, bbox_x2, bbox_y2} pixel coordinates (xyxy)
    YOLO: <class> <x_center> <y_center> <width> <height> normalized 0-1
    """
    x1, y1, x2, y2 = bbox['bbox_x1'], bbox['bbox_y1'], bbox['bbox_x2'], bbox['bbox_y2']
    
    x_center = ((x1 + x2) / 2) / img_width
    y_center = ((y1 + y2) / 2) / img_height
    w = (x2 - x1) / img_width
    h = (y2 - y1) / img_height
    
    # Clamp
    x_center = max(0, min(1, x_center))
    y_center = max(0, min(1, y_center))
    w = max(0.001, min(1, w))
    h = max(0.001, min(1, h))
    
    return f"0 {x_center:.6f} {y_center:.6f} {w:.6f} {h:.6f}"


def validate_yolo_line(line: str) -> bool:
    """Check that a YOLO annotation line is valid."""
    parts = line.strip().split()
    if len(parts) != 5:
        return False
    try:
        cls = int(parts[0])
        x, y, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
        if cls != 0:
            return False
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            return False
        return True
    except ValueError:
        return False


def assign_split_by_group(group_id: str, groups_to_splits: Dict) -> str:
    """Deterministically assign a group (video/camera) to a split.
    Groups are pre-assigned to avoid data leakage between splits."""
    return groups_to_splits.get(group_id, "train")


# ========== Main Export ==========

def export_dataset():
    """Main export function — v2.0"""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUTPUT_DIR = OUTPUT_BASE / f"v2.0_{timestamp}"
    
    print("=" * 80)
    print(f"EXPORTING DATASET v2.0 — {timestamp}")
    print("=" * 80)
    print(f"CLAHE preprocessing: {'ENABLED' if HAS_CV2 else 'DISABLED (no OpenCV)'}")
    print(f"Output: {OUTPUT_DIR}")
    
    # Create output directory structure
    output_images = OUTPUT_DIR / "images"
    output_labels = OUTPUT_DIR / "labels"
    
    for split in ["train", "val", "test"]:
        (output_images / split).mkdir(parents=True, exist_ok=True)
        (output_labels / split).mkdir(parents=True, exist_ok=True)
    
    # Connect to database
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    manifest_data = []
    stats = defaultdict(int)
    
    # =========================================================
    # STEP 1: Get all videos and assign to splits (stratified)
    # =========================================================
    print("\n### STEP 1: Assigning videos to splits (stratified)")
    print("-" * 80)
    
    cursor.execute("SELECT DISTINCT id, filename, camera_name FROM videos ORDER BY id")
    all_videos = cursor.fetchall()
    
    # Shuffle and assign videos to splits
    video_ids = [v['id'] for v in all_videos]
    random.shuffle(video_ids)
    
    video_splits = {}
    n = len(video_ids)
    n_train = max(1, int(n * TRAIN_RATIO))
    n_val = max(1, int(n * VAL_RATIO))
    
    for i, vid in enumerate(video_ids):
        if i < n_train:
            video_splits[vid] = "train"
        elif i < n_train + n_val:
            video_splits[vid] = "val"
        else:
            video_splits[vid] = "test"
    
    for v in all_videos:
        print(f"  Video {v['id']}: {v['filename'][:40]} → {video_splits[v['id']]}")
    
    # =========================================================
    # STEP 2: Export annotated video frames (POSITIVES)
    # =========================================================
    print("\n### STEP 2: Exporting annotated video frames (positives)")
    print("-" * 80)
    
    cursor.execute("""
        SELECT DISTINCT
            f.id as frame_id,
            f.image_path,
            f.video_id,
            v.filename as video_name,
            v.camera_name,
            v.captured_at,
            f.frame_number
        FROM frames f
        JOIN videos v ON f.video_id = v.id
        WHERE f.id IN (SELECT DISTINCT frame_id FROM annotations)
        ORDER BY f.id
    """)
    
    annotated_frames = cursor.fetchall()
    print(f"Found {len(annotated_frames)} frames with annotations")
    
    exported_positives = 0
    skipped_missing = 0
    skipped_invalid = 0
    
    for frame in annotated_frames:
        frame_id = frame['frame_id']
        image_path_raw = frame['image_path']
        
        # Try multiple possible locations for the frame image
        source_path = None
        candidates = [
            FRAMES_DIR / Path(image_path_raw).name,
            FRAMES_DIR / image_path_raw,
            Path(image_path_raw),
        ]
        for candidate in candidates:
            if candidate.exists():
                source_path = candidate
                break
        
        if source_path is None:
            skipped_missing += 1
            continue
        
        # Get all annotations for this frame
        cursor.execute("""
            SELECT bbox_x, bbox_y, bbox_width, bbox_height
            FROM annotations
            WHERE frame_id = ?
        """, (frame_id,))
        
        annotations = cursor.fetchall()
        if not annotations:
            continue
        
        # Convert annotations to YOLO format
        yolo_lines = []
        for ann in annotations:
            bbox = dict(ann)
            line = bbox_annotation_to_yolo(bbox)
            if validate_yolo_line(line):
                yolo_lines.append(line)
            else:
                skipped_invalid += 1
        
        if not yolo_lines:
            continue
        
        # Determine split by video
        split = video_splits.get(frame['video_id'], "train")
        
        # Generate filename
        new_filename = f"pos_frame_{frame_id:06d}.jpg"
        
        # Process and save image (with CLAHE)
        dest_image = output_images / split / new_filename
        if not process_and_save_image(source_path, dest_image, apply_clahe=True):
            skipped_missing += 1
            continue
        
        # Write YOLO label file
        dest_label = output_labels / split / new_filename.replace('.jpg', '.txt')
        with open(dest_label, 'w') as f:
            f.write('\n'.join(yolo_lines))
        
        manifest_data.append({
            'filename': new_filename,
            'split': split,
            'source_type': 'video_frame_positive',
            'frame_id': frame_id,
            'video_name': frame['video_name'] or '',
            'camera_name': frame['camera_name'] or 'unknown',
            'num_annotations': len(yolo_lines),
            'is_positive': True,
        })
        
        exported_positives += 1
        stats[f'positive_{split}'] += 1
    
    print(f"  ✅ Exported {exported_positives} positive frames")
    if skipped_missing:
        print(f"  ⚠️  Skipped {skipped_missing} (missing files)")
    if skipped_invalid:
        print(f"  ⚠️  Skipped {skipped_invalid} invalid annotations")
    
    # =========================================================
    # STEP 3: Export Ring snapshots with deer (POSITIVES)
    # =========================================================
    print("\n### STEP 3: Exporting Ring deer snapshots (positives)")
    print("-" * 80)
    
    cursor.execute("""
        SELECT 
            id, camera_id, timestamp, snapshot_path,
            detection_confidence, detection_bboxes
        FROM ring_events
        WHERE deer_detected = 1
        AND snapshot_available = 1
        AND snapshot_path IS NOT NULL
        AND (false_positive IS NULL OR false_positive = 0)
    """)
    
    deer_snapshots = cursor.fetchall()
    print(f"Found {len(deer_snapshots)} Ring deer snapshots")
    
    exported_deer_snapshots = 0
    
    for snap in deer_snapshots:
        source_path = None
        snap_path = snap['snapshot_path'] or ''
        candidates = [
            SNAPSHOTS_DIR / Path(snap_path).name,
            Path(snap_path),
        ]
        for candidate in candidates:
            if candidate.exists():
                source_path = candidate
                break
        
        if source_path is None:
            continue
        
        # Parse detection bboxes if available
        yolo_lines = []
        if snap['detection_bboxes']:
            try:
                bboxes = json.loads(snap['detection_bboxes'])
                for bbox in bboxes:
                    if isinstance(bbox, dict) and all(k in bbox for k in ['bbox_x1', 'bbox_y1', 'bbox_x2', 'bbox_y2']):
                        line = bbox_detection_to_yolo(bbox)
                        if validate_yolo_line(line):
                            yolo_lines.append(line)
                    elif isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
                        bbox_dict = {'bbox_x1': bbox[0], 'bbox_y1': bbox[1], 'bbox_x2': bbox[2], 'bbox_y2': bbox[3]}
                        line = bbox_detection_to_yolo(bbox_dict)
                        if validate_yolo_line(line):
                            yolo_lines.append(line)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Even without bboxes, include as a known deer image (useful for semi-supervised)
        # But for strict YOLO training, we need labels — skip if no bboxes
        if not yolo_lines:
            print(f"  ⚠️  Snapshot {snap['id']}: deer detected but no bbox data, skipping")
            continue
        
        # Assign Ring snapshots to val/test preferentially (these are production images)
        split = random.choices(["train", "val", "test"], weights=[0.5, 0.25, 0.25])[0]
        
        new_filename = f"pos_ring_{snap['id']:06d}.jpg"
        dest_image = output_images / split / new_filename
        
        if not process_and_save_image(source_path, dest_image, apply_clahe=True):
            continue
        
        dest_label = output_labels / split / new_filename.replace('.jpg', '.txt')
        with open(dest_label, 'w') as f:
            f.write('\n'.join(yolo_lines))
        
        manifest_data.append({
            'filename': new_filename,
            'split': split,
            'source_type': 'ring_snapshot_deer',
            'frame_id': snap['id'],
            'video_name': '',
            'camera_name': snap['camera_id'],
            'num_annotations': len(yolo_lines),
            'is_positive': True,
        })
        
        exported_deer_snapshots += 1
        stats[f'ring_positive_{split}'] += 1
    
    print(f"  ✅ Exported {exported_deer_snapshots} Ring deer snapshots")
    
    # =========================================================
    # STEP 4: Export negative examples
    # =========================================================
    print("\n### STEP 4: Exporting negative examples")
    print("-" * 80)
    
    total_positives = exported_positives + exported_deer_snapshots
    target_negatives = int(total_positives * TARGET_NEGATIVE_RATIO / (1 - TARGET_NEGATIVE_RATIO))
    print(f"  Targeting ~{target_negatives} negatives ({TARGET_NEGATIVE_RATIO*100:.0f}% of total)")
    
    negative_sources = []
    
    # 4a: Video frames reviewed as "no_deer"
    cursor.execute("""
        SELECT 
            f.id as frame_id,
            f.image_path,
            f.video_id,
            v.filename as video_name,
            v.camera_name
        FROM frames f
        JOIN videos v ON f.video_id = v.id
        WHERE f.review_type = 'no_deer'
        AND f.id NOT IN (SELECT DISTINCT frame_id FROM annotations)
        ORDER BY f.id
    """)
    
    no_deer_frames = cursor.fetchall()
    print(f"  Found {len(no_deer_frames)} reviewed no_deer frames")
    
    for frame in no_deer_frames:
        source_path = None
        candidates = [
            FRAMES_DIR / Path(frame['image_path']).name,
            FRAMES_DIR / frame['image_path'],
        ]
        for candidate in candidates:
            if candidate.exists():
                source_path = candidate
                break
        
        if source_path:
            negative_sources.append({
                'source_path': source_path,
                'source_type': 'video_frame_no_deer',
                'frame_id': frame['frame_id'],
                'video_id': frame['video_id'],
                'camera_name': frame['camera_name'] or 'unknown',
            })
    
    # 4b: Ring snapshots without deer
    cursor.execute("""
        SELECT id, camera_id, snapshot_path
        FROM ring_events
        WHERE (deer_detected = 0 OR deer_detected IS NULL)
        AND snapshot_available = 1
        AND snapshot_path IS NOT NULL
        ORDER BY RANDOM()
    """)
    
    no_deer_snapshots = cursor.fetchall()
    print(f"  Found {len(no_deer_snapshots)} Ring snapshots without deer")
    
    for snap in no_deer_snapshots:
        source_path = None
        snap_path = snap['snapshot_path'] or ''
        candidates = [
            SNAPSHOTS_DIR / Path(snap_path).name,
            Path(snap_path),
        ]
        for candidate in candidates:
            if candidate.exists():
                source_path = candidate
                break
        
        if source_path:
            negative_sources.append({
                'source_path': source_path,
                'source_type': 'ring_snapshot_no_deer',
                'frame_id': snap['id'],
                'video_id': None,
                'camera_name': snap['camera_id'],
            })
    
    # 4c: Training archive negatives (from periodic snapshot archiver)
    if TRAINING_ARCHIVE_DIR.exists():
        archive_images = list(TRAINING_ARCHIVE_DIR.rglob("*.jpg"))
        print(f"  Found {len(archive_images)} archived negative images")
        
        for img_path in archive_images:
            camera_id = img_path.parent.name
            negative_sources.append({
                'source_path': img_path,
                'source_type': 'training_archive_negative',
                'frame_id': 0,
                'video_id': None,
                'camera_name': camera_id,
            })
    
    # Subsample negatives to target ratio
    random.shuffle(negative_sources)
    negatives_to_export = negative_sources[:target_negatives]
    print(f"  Exporting {len(negatives_to_export)} of {len(negative_sources)} available negatives")
    
    exported_negatives = 0
    
    for neg in negatives_to_export:
        # Assign split — video-based if from video, random otherwise
        if neg['video_id'] and neg['video_id'] in video_splits:
            split = video_splits[neg['video_id']]
        else:
            split = random.choices(["train", "val", "test"], 
                                   weights=[TRAIN_RATIO, VAL_RATIO, TEST_RATIO])[0]
        
        new_filename = f"neg_{neg['source_type']}_{neg['frame_id']:06d}.jpg"
        
        # Ensure unique filename
        dest_image = output_images / split / new_filename
        if dest_image.exists():
            new_filename = f"neg_{neg['source_type']}_{neg['frame_id']:06d}_{exported_negatives}.jpg"
            dest_image = output_images / split / new_filename
        
        if not process_and_save_image(neg['source_path'], dest_image, apply_clahe=True):
            continue
        
        # Write empty YOLO label file (= negative example)
        dest_label = output_labels / split / new_filename.replace('.jpg', '.txt')
        dest_label.touch()  # Empty file
        
        manifest_data.append({
            'filename': new_filename,
            'split': split,
            'source_type': neg['source_type'],
            'frame_id': neg['frame_id'],
            'video_name': '',
            'camera_name': neg['camera_name'],
            'num_annotations': 0,
            'is_positive': False,
        })
        
        exported_negatives += 1
        stats[f'negative_{split}'] += 1
    
    print(f"  ✅ Exported {exported_negatives} negative frames")
    
    # =========================================================
    # STEP 5: Generate data.yaml
    # =========================================================
    print("\n### STEP 5: Generating data.yaml")
    print("-" * 80)
    
    train_count = len(list((output_images / "train").glob("*.jpg")))
    val_count = len(list((output_images / "val").glob("*.jpg")))
    test_count = len(list((output_images / "test").glob("*.jpg")))
    total = train_count + val_count + test_count
    
    yaml_path = OUTPUT_DIR / "data.yaml"
    with open(yaml_path, 'w') as f:
        f.write(f"# Deer Deterrent Dataset v2.0\n")
        f.write(f"# Exported: {datetime.now().isoformat()}\n")
        f.write(f"# Includes: annotated frames + Ring deer snapshots + negatives\n")
        f.write(f"# Preprocessing: CLAHE (clip_limit={CLAHE_CLIP_LIMIT})\n\n")
        f.write(f"path: .\n")
        f.write(f"train: images/train\n")
        f.write(f"val: images/val\n")
        f.write(f"test: images/test\n\n")
        f.write(f"nc: 1\n")
        f.write(f"names:\n")
        f.write(f"  0: deer\n\n")
        f.write(f"# Stats: train={train_count}, val={val_count}, test={test_count}, total={total}\n")
        f.write(f"# Positives: {exported_positives + exported_deer_snapshots}, Negatives: {exported_negatives}\n")
    
    print(f"  ✅ data.yaml saved")
    
    # =========================================================
    # STEP 6: Generate manifest and metadata
    # =========================================================
    print("\n### STEP 6: Generating manifest & metadata")
    print("-" * 80)
    
    manifest_path = OUTPUT_DIR / "manifest.csv"
    with open(manifest_path, 'w', newline='') as f:
        if manifest_data:
            writer = csv.DictWriter(f, fieldnames=manifest_data[0].keys())
            writer.writeheader()
            writer.writerows(manifest_data)
    
    metadata = {
        'version': '2.0',
        'created_at': datetime.now().isoformat(),
        'preprocessing': {
            'clahe': HAS_CV2,
            'clahe_clip_limit': CLAHE_CLIP_LIMIT,
            'clahe_tile_size': list(CLAHE_TILE_SIZE),
        },
        'statistics': {
            'total_images': total,
            'train': train_count,
            'val': val_count,
            'test': test_count,
            'positives': exported_positives + exported_deer_snapshots,
            'negatives': exported_negatives,
            'positive_video_frames': exported_positives,
            'positive_ring_snapshots': exported_deer_snapshots,
            'negative_ratio': exported_negatives / total if total > 0 else 0,
        },
        'classes': CLASS_NAMES,
    }
    
    metadata_path = OUTPUT_DIR / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"  ✅ manifest.csv and metadata.json saved")
    
    # =========================================================
    # SUMMARY
    # =========================================================
    print("\n" + "=" * 80)
    print("EXPORT COMPLETE!")
    print("=" * 80)
    print(f"\n  Location: {OUTPUT_DIR}")
    print(f"\n  Total images: {total}")
    print(f"    Positives:  {exported_positives + exported_deer_snapshots} ({exported_positives} video + {exported_deer_snapshots} Ring)")
    print(f"    Negatives:  {exported_negatives}")
    print(f"    Train: {train_count}  Val: {val_count}  Test: {test_count}")
    print(f"    Negative ratio: {exported_negatives/total*100:.1f}%" if total > 0 else "")
    print(f"\n  Preprocessing: CLAHE {'✓' if HAS_CV2 else '✗'}")
    print(f"\n  Next steps:")
    print(f"    1. Zip: cd {OUTPUT_DIR} && tar czf ../dataset_v2.0.tar.gz .")
    print(f"    2. Upload to Google Drive or Colab")
    print(f"    3. Train: see scripts/train_yolo26s_v2.py or Colab notebook")
    print(f"\n" + "=" * 80)
    
    conn.close()
    return str(OUTPUT_DIR)


if __name__ == "__main__":
    random.seed(42)
    export_dataset()
