import sqlite3

conn = sqlite3.connect('data/training.db')
cursor = conn.cursor()

# Get all videos with frame and annotation counts
cursor.execute('''
    SELECT 
        v.id, 
        v.filename, 
        COUNT(DISTINCT f.id) as frame_count,
        COUNT(DISTINCT a.id) as annotation_count
    FROM videos v
    LEFT JOIN frames f ON v.id = f.video_id
    LEFT JOIN annotations a ON a.frame_id = f.id
    GROUP BY v.id
    ORDER BY v.id
''')

results = cursor.fetchall()

print("=" * 70)
print(f"{'Video ID':<10} {'Frames':<10} {'Annotations':<15} {'Filename':<35}")
print("=" * 70)

total_frames = 0
total_annotations = 0

for vid, filename, frames, annotations in results:
    print(f"{vid:<10} {frames:<10} {annotations:<15} {filename:<35}")
    total_frames += frames
    total_annotations += annotations

print("=" * 70)
print(f"{'TOTAL':<10} {total_frames:<10} {total_annotations:<15}")
print("=" * 70)

conn.close()
