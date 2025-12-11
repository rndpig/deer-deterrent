import sys
sys.path.insert(0, '/app')
from database import get_connection

conn = get_connection()
cursor = conn.cursor()

print("=== CHECKING ALL VIDEOS ===\n")

# Get all videos
cursor.execute("SELECT id, filename FROM videos ORDER BY id")
videos = cursor.fetchall()

total_fixed = 0
total_frames_fixed = 0

for video in videos:
    video_id = video[0]
    filename = video[1]
    
    # Check frame counts
    cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = ?", (video_id,))
    total_frames = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = ? AND selected_for_training = 1", (video_id,))
    training_frames = cursor.fetchone()[0]
    
    if total_frames > 0:
        if training_frames < total_frames:
            print(f"Video {video_id}: {filename}")
            print(f"  Total frames: {total_frames}")
            print(f"  Training frames: {training_frames}")
            print(f"  ⚠️  Fixing {total_frames - training_frames} frames...")
            
            cursor.execute("UPDATE frames SET selected_for_training = 1 WHERE video_id = ?", (video_id,))
            total_fixed += 1
            total_frames_fixed += (total_frames - training_frames)
            print(f"  ✓ Fixed!\n")
        else:
            print(f"Video {video_id}: {filename} - ✓ OK ({total_frames} frames)\n")

if total_fixed > 0:
    conn.commit()
    print(f"\n{'='*50}")
    print(f"✓ Fixed {total_fixed} videos ({total_frames_fixed} frames)")
    print(f"{'='*50}")
else:
    print("✓ All videos already correct!")

conn.close()
