import sqlite3

conn = sqlite3.connect('data/training.db')
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM videos")
video_count = cursor.fetchone()[0]
print(f"Total videos in database: {video_count}")

cursor.execute("SELECT COUNT(*) FROM frames")
frame_count = cursor.fetchone()[0]
print(f"Total frames in database: {frame_count}")

cursor.execute("SELECT COUNT(*) FROM annotations")
annotation_count = cursor.fetchone()[0]
print(f"Total annotations in database: {annotation_count}")

print("\nVideos:")
cursor.execute("SELECT id, filename FROM videos ORDER BY id LIMIT 10")
for vid, fn in cursor.fetchall():
    print(f"  {vid}: {fn}")

conn.close()
