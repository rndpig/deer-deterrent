import sqlite3

conn = sqlite3.connect('data/training.db')
cursor = conn.cursor()

video_id = 5

# Check frames
cursor.execute('SELECT COUNT(*) FROM frames WHERE video_id = ?', (video_id,))
frame_count = cursor.fetchone()[0]
print(f"Total frames for video {video_id}: {frame_count}")

# Show some sample frames
cursor.execute('SELECT id, frame_number, image_path, reviewed FROM frames WHERE video_id = ? LIMIT 5', (video_id,))
sample_frames = cursor.fetchall()
print("\nSample frames:")
for fid, fnum, path, reviewed in sample_frames:
    print(f"  Frame {fid}: number={fnum}, reviewed={reviewed}, path={path}")

# Check annotations (by frame_id)
cursor.execute('''
    SELECT COUNT(*) 
    FROM annotations a 
    JOIN frames f ON a.frame_id = f.id 
    WHERE f.video_id = ?
''', (video_id,))
annotation_count = cursor.fetchone()[0]
print(f"\nTotal annotations for video {video_id}: {annotation_count}")

# Show sample annotations
cursor.execute('''
    SELECT a.id, a.frame_id, a.bbox_data 
    FROM annotations a 
    JOIN frames f ON a.frame_id = f.id 
    WHERE f.video_id = ? 
    LIMIT 3
''', (video_id,))
sample_annots = cursor.fetchall()
print("\nSample annotations:")
for aid, frame_id, bbox in sample_annots:
    print(f"  Annotation {aid}: frame={frame_id}, bbox={bbox}")

# Check all videos with their frame counts
cursor.execute('''
    SELECT v.id, v.filename, COUNT(f.id) as frame_count
    FROM videos v
    LEFT JOIN frames f ON v.id = f.video_id
    GROUP BY v.id
    ORDER BY v.id
''')
all_videos = cursor.fetchall()
print("\nAll videos:")
for vid, filename, fcount in all_videos:
    print(f"  Video {vid} ({filename}): {fcount} frames")

conn.close()
