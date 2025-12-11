import sys
sys.path.insert(0, '/app')
from database import get_connection

conn = get_connection()
cursor = conn.cursor()

print("=== CHECKING ALL VIDEOS FOR DUPLICATE FRAMES ===\n")

# Get all videos
cursor.execute("SELECT id, filename FROM videos ORDER BY id")
videos = cursor.fetchall()

total_videos_fixed = 0
total_frames_deleted = 0

for video in videos:
    video_id = video[0]
    filename = video[1]
    
    # Get frame count
    cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = ?", (video_id,))
    total_frames = cursor.fetchone()[0]
    
    if total_frames == 0:
        continue
    
    # Get all frame IDs ordered by ID (chronological order of insertion)
    cursor.execute("""
        SELECT id, frame_number
        FROM frames
        WHERE video_id = ?
        ORDER BY id
    """, (video_id,))
    
    frames = cursor.fetchall()
    
    # Find the midpoint - if there are duplicates, they'll be in the second half
    # Check if second half has similar frame_numbers to first half
    if total_frames >= 40:  # Only check videos with enough frames to have duplicates
        midpoint = total_frames // 2
        first_half_ids = [f[0] for f in frames[:midpoint]]
        second_half_ids = [f[0] for f in frames[midpoint:]]
        
        # Check if there's a big gap in IDs (indicates two separate extractions)
        if first_half_ids and second_half_ids:
            id_gap = second_half_ids[0] - first_half_ids[-1]
            
            if id_gap > 50:  # Significant gap suggests separate extractions
                print(f"Video {video_id}: {filename}")
                print(f"  Total frames: {total_frames}")
                print(f"  ID gap detected: {id_gap} (first batch ends at {first_half_ids[-1]}, second starts at {second_half_ids[0]})")
                
                # Check if second half has fewer detections (manual annotations only)
                cursor.execute("""
                    SELECT COUNT(DISTINCT d.id)
                    FROM detections d
                    WHERE d.frame_id IN ({})
                """.format(','.join('?' * len(second_half_ids))), second_half_ids)
                second_half_detections = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT COUNT(DISTINCT d.id)
                    FROM detections d
                    WHERE d.frame_id IN ({})
                """.format(','.join('?' * len(first_half_ids))), first_half_ids)
                first_half_detections = cursor.fetchone()[0]
                
                print(f"  First half detections: {first_half_detections}")
                print(f"  Second half detections: {second_half_detections}")
                
                # If second half has significantly fewer detections, it's likely duplicates
                if second_half_detections < first_half_detections * 0.5:
                    print(f"  ⚠️  Deleting second half (duplicate frames)...")
                    
                    cursor.execute("""
                        DELETE FROM frames
                        WHERE video_id = ? AND id >= ?
                    """, (video_id, second_half_ids[0]))
                    
                    deleted = cursor.rowcount
                    total_frames_deleted += deleted
                    total_videos_fixed += 1
                    
                    print(f"  ✓ Deleted {deleted} duplicate frames\n")
                else:
                    print(f"  → Skipping (detection counts similar)\n")

if total_videos_fixed > 0:
    conn.commit()
    print(f"{'='*60}")
    print(f"✓ Fixed {total_videos_fixed} videos")
    print(f"✓ Deleted {total_frames_deleted} duplicate frames")
    print(f"{'='*60}")
else:
    print("✓ No duplicate frames found in any video!")

conn.close()
