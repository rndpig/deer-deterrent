import sys
sys.path.insert(0, '/app')
from database import get_connection

conn = get_connection()
cursor = conn.cursor()

video_id = 7

print("Checking video 7 (RingVideo_20251120_064055.mp4)...\n")

# Get all frames ordered by ID
cursor.execute("""
    SELECT id, frame_number
    FROM frames
    WHERE video_id = ?
    ORDER BY id
""", (video_id,))

frames = cursor.fetchall()
print(f"Total frames: {len(frames)}")

if len(frames) >= 54:
    midpoint = 27
    first_half_ids = [f[0] for f in frames[:midpoint]]
    second_half_ids = [f[0] for f in frames[midpoint:]]
    
    print(f"\nFirst half (0-26): IDs {first_half_ids[0]} to {first_half_ids[-1]}")
    print(f"Second half (27-53): IDs {second_half_ids[0]} to {second_half_ids[-1]}")
    
    # Check annotations in each half
    cursor.execute("""
        SELECT COUNT(*)
        FROM annotations
        WHERE frame_id IN ({})
    """.format(','.join('?' * len(first_half_ids))), first_half_ids)
    first_annotations = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*)
        FROM annotations
        WHERE frame_id IN ({})
    """.format(','.join('?' * len(second_half_ids))), second_half_ids)
    second_annotations = cursor.fetchone()[0]
    
    print(f"\nFirst half annotations: {first_annotations}")
    print(f"Second half annotations: {second_annotations}")
    
    print(f"\n⚠️  Deleting first half (frames 0-26, IDs {first_half_ids[0]}-{first_half_ids[-1]})...")
    
    cursor.execute("""
        DELETE FROM frames
        WHERE video_id = ? AND id <= ?
    """, (video_id, first_half_ids[-1]))
    
    deleted = cursor.rowcount
    conn.commit()
    
    print(f"✓ Deleted {deleted} duplicate frames")
    
    # Verify remaining count
    cursor.execute("SELECT COUNT(*) FROM frames WHERE video_id = ?", (video_id,))
    remaining = cursor.fetchone()[0]
    print(f"✓ Remaining frames: {remaining}")

conn.close()
