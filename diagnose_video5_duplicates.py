import sys
sys.path.insert(0, '/app')
from database import get_connection

conn = get_connection()
cursor = conn.cursor()

# Check video 5
video_id = 5

cursor.execute("SELECT filename FROM videos WHERE id = ?", (video_id,))
video = cursor.fetchone()
print(f"Video: {video[0]}\n")

# Get all frames ordered by frame_number
cursor.execute("""
    SELECT id, frame_number, selected_for_training, has_detections, image_path
    FROM frames 
    WHERE video_id = ?
    ORDER BY frame_number
""", (video_id,))

frames = cursor.fetchall()
print(f"Total frames in database: {len(frames)}\n")

# Check for duplicates by frame_number
frame_numbers = {}
for frame in frames:
    frame_num = frame[1]
    if frame_num not in frame_numbers:
        frame_numbers[frame_num] = []
    frame_numbers[frame_num].append({
        'id': frame[0],
        'has_detections': frame[3],
        'image_path': frame[4]
    })

duplicates = {k: v for k, v in frame_numbers.items() if len(v) > 1}

if duplicates:
    print(f"⚠️  Found {len(duplicates)} frame numbers with duplicates:\n")
    
    for frame_num, instances in sorted(duplicates.items())[:10]:
        print(f"Frame number {frame_num} has {len(instances)} entries:")
        for inst in instances:
            # Check if it has detections
            cursor.execute("SELECT COUNT(*) FROM detections WHERE frame_id = ?", (inst['id'],))
            det_count = cursor.fetchone()[0]
            
            # Check if it has annotations
            cursor.execute("SELECT COUNT(*) FROM annotations WHERE frame_id = ?", (inst['id'],))
            ann_count = cursor.fetchone()[0]
            
            print(f"  Frame ID {inst['id']}: {det_count} detections, {ann_count} annotations")
        print()
    
    # Determine which ones to keep
    print("\n" + "="*50)
    print("RECOMMENDATION:")
    print("="*50)
    print("Keep frames WITH detections (auto-detected)")
    print("Delete frames WITHOUT detections (duplicates with only manual boxes)")
else:
    print("✓ No duplicate frame numbers found")

conn.close()
