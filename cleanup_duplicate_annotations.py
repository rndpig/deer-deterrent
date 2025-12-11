import sys
sys.path.insert(0, '/app')
from database import get_connection

conn = get_connection()
cursor = conn.cursor()

print("=== CHECKING FOR DUPLICATE ANNOTATIONS ===\n")

# Find frames with excessive annotations
cursor.execute("""
    SELECT frame_id, COUNT(*) as count
    FROM annotations
    GROUP BY frame_id
    HAVING COUNT(*) > 10
    ORDER BY COUNT(*) DESC
    LIMIT 20
""")

problem_frames = cursor.fetchall()

if not problem_frames:
    print("✓ No frames with excessive annotations found!")
else:
    print(f"Found {len(problem_frames)} frames with >10 annotations:\n")
    
    total_deleted = 0
    for row in problem_frames:
        frame_id = row[0]
        count = row[1]
        
        # Get frame info
        cursor.execute("""
            SELECT f.id, f.frame_number, f.video_id, v.filename
            FROM frames f
            JOIN videos v ON f.video_id = v.id
            WHERE f.id = ?
        """, (frame_id,))
        frame_info = cursor.fetchone()
        
        if frame_info:
            print(f"Frame {frame_info[1]} in {frame_info[3]}: {count} annotations")
            print(f"  Deleting all annotations for frame {frame_id}...")
            
            cursor.execute("DELETE FROM annotations WHERE frame_id = ?", (frame_id,))
            total_deleted += count
            print(f"  ✓ Deleted {count} duplicate annotations\n")
    
    conn.commit()
    print(f"{'='*50}")
    print(f"✓ Total annotations deleted: {total_deleted}")
    print(f"{'='*50}")
    print("\nYou will need to re-annotate these frames manually.")

conn.close()
