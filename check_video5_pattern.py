import sys
sys.path.insert(0, '/app')
from database import get_connection

conn = get_connection()
cursor = conn.cursor()

video_id = 5

print("Checking frames 1-20 and 47-66 for pattern:\n")

for i in range(1, 21):
    # Get frame i
    cursor.execute("""
        SELECT id, image_path 
        FROM frames 
        WHERE video_id = ? AND frame_number = ?
        ORDER BY id
    """, (video_id, i * 30))  # Assuming 30 frame interval
    
    frames_low = cursor.fetchall()
    
    # Get frame i+46
    cursor.execute("""
        SELECT id, image_path
        FROM frames
        WHERE video_id = ? AND frame_number = ?
        ORDER BY id
    """, (video_id, (i + 46) * 30))
    
    frames_high = cursor.fetchall()
    
    if frames_low and frames_high:
        print(f"Frame number {i*30}: {len(frames_low)} entries")
        print(f"Frame number {(i+46)*30}: {len(frames_high)} entries")
        
        # Check if image paths are the same
        if frames_low[0][1] == frames_high[0][1]:
            print(f"  ⚠️  SAME IMAGE FILE!")
        print()

# Actually, let me just list all frames with their frame_number
print("\n" + "="*60)
print("ALL FRAMES:")
print("="*60)

cursor.execute("""
    SELECT id, frame_number, image_path
    FROM frames
    WHERE video_id = ?
    ORDER BY id
""", (video_id,))

frames = cursor.fetchall()
for i, frame in enumerate(frames, 1):
    print(f"{i:3d}. Frame ID {frame[0]:4d}, frame_number={frame[1]:4d}, {frame[2].split('/')[-1]}")

conn.close()
