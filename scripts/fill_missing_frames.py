#!/usr/bin/env python3
"""
One-time migration script to fill in missing frames for videos.
Extracts frames that are missing from the sequence while preserving existing frames and annotations.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import backend modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import cv2
from backend import database as db

def fill_missing_frames_for_video(video_id: int):
    """Fill in missing frames for a specific video."""
    print(f"\nProcessing video {video_id}...")
    
    video = db.get_video(video_id)
    if not video:
        print(f"  ❌ Video {video_id} not found")
        return False
    
    video_path = Path(video.get('video_path', ''))
    if not video_path.exists():
        print(f"  ❌ Video file not found: {video_path}")
        return False
    
    # Get existing frames
    existing_frames = db.get_frames_for_video(video_id)
    existing_frame_numbers = set(f['frame_number'] for f in existing_frames)
    
    if not existing_frame_numbers:
        print(f"  ℹ️  No frames exist yet, skipping")
        return False
    
    # Determine the interval pattern from existing frames
    sorted_frames = sorted(existing_frame_numbers)
    if len(sorted_frames) < 2:
        print(f"  ℹ️  Only one frame exists, can't determine pattern")
        return False
    
    # Find the expected interval (most common gap between consecutive frames)
    gaps = [sorted_frames[i+1] - sorted_frames[i] for i in range(len(sorted_frames)-1)]
    # Filter out large gaps (likely at video boundaries)
    small_gaps = [g for g in gaps if g <= 30]  # Assume max interval is 30 frames
    if not small_gaps:
        print(f"  ℹ️  Can't determine frame interval pattern")
        return False
    
    # Most common small gap is our interval
    from collections import Counter
    interval = Counter(small_gaps).most_common(1)[0][0]
    
    print(f"  📊 Detected frame interval: {interval}")
    print(f"  📊 Existing frames: {len(existing_frames)}")
    
    # Determine expected frames based on interval
    min_frame = min(existing_frame_numbers)
    max_frame = max(existing_frame_numbers)
    expected_frames = set(range(min_frame, max_frame + 1, interval))
    
    missing_frames = expected_frames - existing_frame_numbers
    
    if not missing_frames:
        print(f"  ✅ No missing frames found")
        return True
    
    print(f"  🔍 Missing frames: {sorted(missing_frames)}")
    
    # Open video
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  ❌ Could not open video file")
        return False
    
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    frames_dir = Path("data/training_frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    
    added_count = 0
    
    # Extract only missing frames
    for frame_num in sorted(missing_frames):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        
        if not ret:
            print(f"    ⚠️  Could not read frame {frame_num}")
            continue
        
        # Save frame
        frame_filename = f"video_{video_id}_frame_{frame_num}.jpg"
        frame_path = frames_dir / frame_filename
        cv2.imwrite(str(frame_path), frame)
        
        # Calculate timestamp
        timestamp_sec = frame_num / fps
        
        # Store in database
        frame_id = db.add_frame(
            video_id=video_id,
            frame_number=frame_num,
            timestamp_in_video=timestamp_sec,
            image_path=str(frame_path),
            has_detections=False
        )
        
        # Mark as selected for training
        db.mark_frame_for_training(frame_id)
        added_count += 1
    
    cap.release()
    
    print(f"  ✅ Added {added_count} missing frames")
    
    # Clear the fully_annotated flag for this video
    db.clear_video_annotation_flag(video_id)
    print(f"  🔄 Cleared annotation completion flag")
    
    return True

def main():
    print("🔧 Frame Migration Script")
    print("=" * 50)
    
    # Get all videos
    videos = db.get_all_videos()
    print(f"\nFound {len(videos)} videos\n")
    
    processed = 0
    updated = 0
    
    for video in videos:
        video_id = video['id']
        
        # Only process videos that have frames
        existing_frames = db.get_frames_for_video(video_id)
        if not existing_frames:
            continue
        
        processed += 1
        
        if fill_missing_frames_for_video(video_id):
            updated += 1
    
    print("\n" + "=" * 50)
    print(f"✅ Migration complete!")
    print(f"   Processed: {processed} videos with frames")
    print(f"   Updated: {updated} videos")
    print("=" * 50)

if __name__ == "__main__":
    main()
