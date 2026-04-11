#!/usr/bin/env python3
"""
Comprehensive diagnostic script for training data inventory.
Reviews ALL sources of training data for deer detection model retraining.

Data Sources:
1. ring_events table - snapshots from live camera monitoring
2. frames table - extracted frames from uploaded videos  
3. detections table - auto-detected bboxes on video frames
4. annotations table - manual annotations on video frames
"""

import sqlite3
import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Database path
DB_PATH = Path(__file__).parent.parent / "backend" / "data" / "training.db"

def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def get_camera_name(camera_id):
    """Map camera_id to friendly name."""
    CAMERA_MAP = {
        '10cea9e4511f': 'Woods',      # Was Side, moved to barn
        'c4dbad08f862': 'Side',       # New Floodlight Cam Pro
        '587a624d3fae': 'Driveway',
        '4439c4de7a79': 'Front Door',
        'f045dae9383a': 'Back',
    }
    return CAMERA_MAP.get(camera_id, camera_id[:12] if camera_id else 'Unknown')

def analyze_ring_events():
    """Analyze ring_events table - snapshots from live monitoring."""
    print_section("RING_EVENTS TABLE (Live Camera Snapshots)")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total events
    cursor.execute("SELECT COUNT(*) FROM ring_events")
    total = cursor.fetchone()[0]
    print(f"\nTotal ring_events: {total}")
    
    # By camera
    print("\nBy Camera:")
    cursor.execute("""
        SELECT camera_id, COUNT(*) as count,
               SUM(CASE WHEN deer_detected = 1 THEN 1 ELSE 0 END) as deer_positive,
               SUM(CASE WHEN detection_bboxes IS NOT NULL AND detection_bboxes != '' AND detection_bboxes != '[]' THEN 1 ELSE 0 END) as has_bboxes
        FROM ring_events
        GROUP BY camera_id
        ORDER BY count DESC
    """)
    for row in cursor.fetchall():
        cam_name = get_camera_name(row['camera_id'])
        print(f"  {cam_name:15s}: {row['count']:6d} events, {row['deer_positive']:4d} deer+, {row['has_bboxes']:4d} with bboxes")
    
    # Count actual bboxes in ring_events
    print("\nBounding Box Analysis in ring_events:")
    cursor.execute("""
        SELECT camera_id, detection_bboxes 
        FROM ring_events 
        WHERE detection_bboxes IS NOT NULL AND detection_bboxes != '' AND detection_bboxes != '[]'
    """)
    
    bbox_counts = defaultdict(lambda: {'events': 0, 'bboxes': 0})
    for row in cursor.fetchall():
        cam = get_camera_name(row['camera_id'])
        try:
            bboxes = json.loads(row['detection_bboxes'])
            if bboxes:
                bbox_counts[cam]['events'] += 1
                bbox_counts[cam]['bboxes'] += len(bboxes)
        except (json.JSONDecodeError, TypeError):
            pass
    
    for cam, data in sorted(bbox_counts.items(), key=lambda x: x[1]['bboxes'], reverse=True):
        print(f"  {cam}: {data['events']} events with {data['bboxes']} total bboxes")
    
    # User confirmed events
    cursor.execute("""
        SELECT camera_id, COUNT(*) as confirmed
        FROM ring_events
        WHERE user_confirmed = 1
        GROUP BY camera_id
    """)
    confirmed = cursor.fetchall()
    if confirmed:
        print("\nUser-Confirmed Events:")
        for row in confirmed:
            print(f"  {get_camera_name(row['camera_id'])}: {row['confirmed']}")
    
    # Check for archived events
    cursor.execute("SELECT COUNT(*) FROM ring_events WHERE archived = 1")
    archived = cursor.fetchone()[0]
    print(f"\nArchived events: {archived}")
    
    conn.close()

def analyze_video_frames():
    """Analyze frames from uploaded videos."""
    print_section("VIDEO FRAMES (Uploaded Videos)")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total frames
    cursor.execute("SELECT COUNT(*) FROM frames")
    total_frames = cursor.fetchone()[0]
    print(f"\nTotal video frames: {total_frames}")
    
    # By video/camera
    print("\nBy Video (top 15 by frame count):")
    cursor.execute("""
        SELECT v.id, v.camera_name, v.filename, COUNT(f.id) as frame_count,
               v.captured_at, v.upload_date
        FROM videos v
        JOIN frames f ON v.id = f.video_id
        GROUP BY v.id
        ORDER BY frame_count DESC
        LIMIT 15
    """)
    for row in cursor.fetchall():
        ts = row['captured_at'] or row['upload_date'] or 'unknown date'
        print(f"  [{row['id']:2d}] {row['camera_name'] or 'Unknown':12s} {row['filename'][:40]:40s} {row['frame_count']:3d} frames ({ts[:10]})")
    
    # Aggregate by camera
    print("\nAggregate by Camera:")
    cursor.execute("""
        SELECT v.camera_name, COUNT(DISTINCT v.id) as videos, COUNT(f.id) as frames
        FROM videos v
        JOIN frames f ON v.id = f.video_id
        GROUP BY v.camera_name
        ORDER BY frames DESC
    """)
    for row in cursor.fetchall():
        cam = row['camera_name'] or 'Unknown'
        print(f"  {cam:15s}: {row['videos']:3d} videos, {row['frames']:4d} frames")
    
    conn.close()

def analyze_detections():
    """Analyze auto-detections on video frames."""
    print_section("DETECTIONS TABLE (Auto-Detected Bboxes on Video Frames)")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total detections
    cursor.execute("SELECT COUNT(*) FROM detections")
    total = cursor.fetchone()[0]
    print(f"\nTotal auto-detections: {total}")
    
    # By camera
    print("\nBy Camera:")
    cursor.execute("""
        SELECT v.camera_name, COUNT(d.id) as detections, COUNT(DISTINCT f.id) as frames_with_det
        FROM detections d
        JOIN frames f ON d.frame_id = f.id
        JOIN videos v ON f.video_id = v.id
        GROUP BY v.camera_name
        ORDER BY detections DESC
    """)
    for row in cursor.fetchall():
        cam = row['camera_name'] or 'Unknown'
        print(f"  {cam:15s}: {row['detections']:4d} bboxes on {row['frames_with_det']} frames")
    
    # Confidence distribution
    print("\nConfidence Distribution:")
    cursor.execute("""
        SELECT 
            SUM(CASE WHEN confidence >= 0.8 THEN 1 ELSE 0 END) as high,
            SUM(CASE WHEN confidence >= 0.6 AND confidence < 0.8 THEN 1 ELSE 0 END) as medium,
            SUM(CASE WHEN confidence >= 0.4 AND confidence < 0.6 THEN 1 ELSE 0 END) as low,
            SUM(CASE WHEN confidence < 0.4 THEN 1 ELSE 0 END) as very_low
        FROM detections
    """)
    row = cursor.fetchone()
    print(f"  High (>=0.8): {row['high']}, Medium (0.6-0.8): {row['medium']}, Low (0.4-0.6): {row['low']}, Very Low (<0.4): {row['very_low']}")
    
    conn.close()

def analyze_annotations():
    """Analyze manual annotations on video frames."""
    print_section("ANNOTATIONS TABLE (Manual Bboxes on Video Frames)")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Total annotations
    cursor.execute("SELECT COUNT(*) FROM annotations")
    total = cursor.fetchone()[0]
    print(f"\nTotal manual annotations: {total}")
    
    # By camera
    print("\nBy Camera:")
    cursor.execute("""
        SELECT v.camera_name, COUNT(a.id) as annotations, COUNT(DISTINCT f.id) as frames_annotated
        FROM annotations a
        JOIN frames f ON a.frame_id = f.id
        JOIN videos v ON f.video_id = v.id
        GROUP BY v.camera_name
        ORDER BY annotations DESC
    """)
    for row in cursor.fetchall():
        cam = row['camera_name'] or 'Unknown'
        print(f"  {cam:15s}: {row['annotations']:4d} bboxes on {row['frames_annotated']} frames")
    
    # By video
    print("\nBy Video (top 10 by annotation count):")
    cursor.execute("""
        SELECT v.camera_name, v.filename, COUNT(a.id) as annotations
        FROM annotations a
        JOIN frames f ON a.frame_id = f.id
        JOIN videos v ON f.video_id = v.id
        GROUP BY v.id
        ORDER BY annotations DESC
        LIMIT 10
    """)
    for row in cursor.fetchall():
        cam = row['camera_name'] or 'Unknown'
        print(f"  {cam:12s} {row['filename'][:35]:35s} {row['annotations']:4d} bboxes")
    
    conn.close()

def analyze_snapshot_files():
    """Check actual snapshot files on disk."""
    print_section("SNAPSHOT FILES ON DISK")
    
    # Check multiple possible locations
    snapshot_dirs = [
        Path(__file__).parent.parent / "backend" / "data" / "snapshots",
        Path(__file__).parent.parent / "dell-deployment" / "data" / "snapshots",
        Path(__file__).parent.parent / "backend" / "data" / "frames",
    ]
    
    for snap_dir in snapshot_dirs:
        if snap_dir.exists():
            files = list(snap_dir.glob("*.jpg")) + list(snap_dir.glob("*.png"))
            print(f"\n{snap_dir.relative_to(snap_dir.parent.parent)}:")
            print(f"  Total image files: {len(files)}")
            
            # Group by camera if possible (based on filename patterns)
            camera_counts = defaultdict(int)
            for f in files:
                name = f.name.lower()
                if 'side' in name:
                    camera_counts['Side'] += 1
                elif 'driveway' in name:
                    camera_counts['Driveway'] += 1
                elif 'woods' in name:
                    camera_counts['Woods'] += 1
                elif 'back' in name:
                    camera_counts['Back'] += 1
                elif 'front' in name:
                    camera_counts['Front Door'] += 1
                else:
                    camera_counts['Unknown'] += 1
            
            if camera_counts:
                print("  By camera (filename-based):")
                for cam, count in sorted(camera_counts.items(), key=lambda x: x[1], reverse=True):
                    print(f"    {cam}: {count}")
        else:
            print(f"\n{snap_dir}: NOT FOUND")

def training_data_summary():
    """Summarize all usable training data."""
    print_section("TRAINING DATA SUMMARY")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n" + "-"*50)
    print("POSITIVE SAMPLES (Deer Present)")
    print("-"*50)
    
    # From ring_events with bboxes
    cursor.execute("""
        SELECT camera_id, detection_bboxes 
        FROM ring_events 
        WHERE deer_detected = 1 
        AND detection_bboxes IS NOT NULL 
        AND detection_bboxes != '' 
        AND detection_bboxes != '[]'
    """)
    
    ring_positives = defaultdict(lambda: {'images': 0, 'bboxes': 0})
    for row in cursor.fetchall():
        cam = get_camera_name(row['camera_id'])
        try:
            bboxes = json.loads(row['detection_bboxes'])
            if bboxes:
                ring_positives[cam]['images'] += 1
                ring_positives[cam]['bboxes'] += len(bboxes)
        except:
            pass
    
    print("\nFrom ring_events (live snapshots):")
    ring_total_images = 0
    ring_total_bboxes = 0
    for cam, data in sorted(ring_positives.items(), key=lambda x: x[1]['bboxes'], reverse=True):
        print(f"  {cam:15s}: {data['images']:4d} images, {data['bboxes']:4d} bboxes")
        ring_total_images += data['images']
        ring_total_bboxes += data['bboxes']
    print(f"  {'TOTAL':15s}: {ring_total_images:4d} images, {ring_total_bboxes:4d} bboxes")
    
    # From video frames with detections
    cursor.execute("""
        SELECT v.camera_name, COUNT(DISTINCT f.id) as frames, COUNT(d.id) as bboxes
        FROM frames f
        JOIN detections d ON f.id = d.frame_id
        JOIN videos v ON f.video_id = v.id
        GROUP BY v.camera_name
    """)
    
    print("\nFrom video frames (auto-detected):")
    video_det_total_frames = 0
    video_det_total_bboxes = 0
    for row in cursor.fetchall():
        cam = row['camera_name'] or 'Unknown'
        print(f"  {cam:15s}: {row['frames']:4d} frames, {row['bboxes']:4d} bboxes")
        video_det_total_frames += row['frames']
        video_det_total_bboxes += row['bboxes']
    print(f"  {'TOTAL':15s}: {video_det_total_frames:4d} frames, {video_det_total_bboxes:4d} bboxes")
    
    # From video frames with manual annotations
    cursor.execute("""
        SELECT v.camera_name, COUNT(DISTINCT f.id) as frames, COUNT(a.id) as bboxes
        FROM frames f
        JOIN annotations a ON f.id = a.frame_id
        JOIN videos v ON f.video_id = v.id
        GROUP BY v.camera_name
    """)
    
    print("\nFrom video frames (manual annotations):")
    video_ann_total_frames = 0
    video_ann_total_bboxes = 0
    for row in cursor.fetchall():
        cam = row['camera_name'] or 'Unknown'
        print(f"  {cam:15s}: {row['frames']:4d} frames, {row['bboxes']:4d} bboxes")
        video_ann_total_frames += row['frames']
        video_ann_total_bboxes += row['bboxes']
    print(f"  {'TOTAL':15s}: {video_ann_total_frames:4d} frames, {video_ann_total_bboxes:4d} bboxes")
    
    print("\n" + "-"*50)
    print("NEGATIVE SAMPLES (No Deer)")
    print("-"*50)
    
    # Ring events without deer
    cursor.execute("""
        SELECT camera_id, COUNT(*) as count
        FROM ring_events
        WHERE deer_detected = 0 OR deer_detected IS NULL
        GROUP BY camera_id
    """)
    print("\nFrom ring_events (no deer detected):")
    for row in cursor.fetchall():
        print(f"  {get_camera_name(row['camera_id']):15s}: {row['count']:4d} images")
    
    # Video frames without detections or annotations
    cursor.execute("""
        SELECT v.camera_name, COUNT(f.id) as frames
        FROM frames f
        JOIN videos v ON f.video_id = v.id
        WHERE f.id NOT IN (SELECT frame_id FROM detections)
        AND f.id NOT IN (SELECT frame_id FROM annotations)
        GROUP BY v.camera_name
    """)
    print("\nFrom video frames (no deer):")
    for row in cursor.fetchall():
        cam = row['camera_name'] or 'Unknown'
        print(f"  {cam:15s}: {row['frames']:4d} frames")
    
    print("\n" + "-"*50)
    print("GRAND TOTALS FOR TRAINING")
    print("-"*50)
    
    total_positive_images = ring_total_images + video_det_total_frames + video_ann_total_frames
    total_bboxes = ring_total_bboxes + video_det_total_bboxes + video_ann_total_bboxes
    
    print(f"\nPositive images (with deer): ~{total_positive_images} (some overlap expected)")
    print(f"Total bounding boxes: ~{total_bboxes} (some overlap between detections/annotations)")
    
    # Camera breakdown combined
    print("\nCombined by Camera (ring_events + video all sources):")
    combined = defaultdict(lambda: {'ring_images': 0, 'ring_bboxes': 0, 'video_frames': 0, 'video_bboxes': 0})
    
    for cam, data in ring_positives.items():
        combined[cam]['ring_images'] = data['images']
        combined[cam]['ring_bboxes'] = data['bboxes']
    
    cursor.execute("""
        SELECT v.camera_name, 
               COUNT(DISTINCT f.id) as frames,
               (SELECT COUNT(*) FROM detections d WHERE d.frame_id IN (SELECT id FROM frames WHERE video_id = v.id)) +
               (SELECT COUNT(*) FROM annotations a WHERE a.frame_id IN (SELECT id FROM frames WHERE video_id = v.id)) as bboxes
        FROM videos v
        JOIN frames f ON v.id = f.video_id
        WHERE f.id IN (SELECT frame_id FROM detections) OR f.id IN (SELECT frame_id FROM annotations)
        GROUP BY v.camera_name
    """)
    for row in cursor.fetchall():
        cam = row['camera_name'] or 'Unknown'
        combined[cam]['video_frames'] = row['frames']
        combined[cam]['video_bboxes'] = row['bboxes']
    
    for cam in sorted(combined.keys()):
        data = combined[cam]
        total_imgs = data['ring_images'] + data['video_frames']
        total_bb = data['ring_bboxes'] + data['video_bboxes']
        print(f"  {cam:15s}: {total_imgs:4d} images, {total_bb:4d} bboxes (ring: {data['ring_images']}/{data['ring_bboxes']}, video: {data['video_frames']}/{data['video_bboxes']})")
    
    conn.close()

def check_export_script_compatibility():
    """Check what the export script would actually export."""
    print_section("EXPORT SCRIPT COMPATIBILITY")
    
    export_script = Path(__file__).parent / "export_dataset_v2.py"
    if export_script.exists():
        print(f"\nExport script found: {export_script.name}")
        print("(Run 'python scripts/export_dataset_v2.py --dry-run' for detailed export preview)")
    else:
        print(f"\nExport script NOT FOUND at {export_script}")

def main():
    print("\n" + "="*60)
    print("  DEER DETERRENT TRAINING DATA DIAGNOSTIC")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    if not DB_PATH.exists():
        print(f"\nERROR: Database not found at {DB_PATH}")
        print("This script should be run on the server or with the database available.")
        return
    
    print(f"\nDatabase: {DB_PATH}")
    
    analyze_ring_events()
    analyze_video_frames()
    analyze_detections()
    analyze_annotations()
    analyze_snapshot_files()
    training_data_summary()
    check_export_script_compatibility()
    
    print("\n" + "="*60)
    print("  END OF DIAGNOSTIC")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
