"""Fix selected_for_training flag for all frames in video 28."""
import sys
sys.path.insert(0, '/home/rndpig/deer-deterrent')

from backend.database import get_connection

def fix_training_frames():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get all frames for video 28
    cursor.execute("SELECT id, frame_number FROM frames WHERE video_id = 28 ORDER BY frame_number")
    frames = cursor.fetchall()
    
    print(f"Found {len(frames)} frames for video 28")
    
    # Check current state
    cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = 28 AND selected_for_training = 1")
    training_count = cursor.fetchone()[0]
    print(f"Currently {training_count} frames marked for training")
    
    # Update all frames to be selected for training
    cursor.execute("UPDATE frames SET selected_for_training = 1 WHERE video_id = 28")
    conn.commit()
    
    # Verify
    cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = 28 AND selected_for_training = 1")
    new_count = cursor.fetchone()[0]
    print(f"After update: {new_count} frames marked for training")
    
    conn.close()
    print("✓ Done!")

if __name__ == '__main__':
    fix_training_frames()
