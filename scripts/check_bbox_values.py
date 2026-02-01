import sqlite3
from pathlib import Path

DB_PATH = Path("/home/rndpig/deer-deterrent/backend/data/training.db")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check bbox values
cursor.execute("""
    SELECT f.image_path, a.bbox_x, a.bbox_y, a.bbox_width, a.bbox_height
    FROM annotations a
    JOIN frames f ON a.frame_id = f.id
    LIMIT 10
""")

print("Sample bbox values from database:")
print("-" * 80)
for row in cursor.fetchall():
    print(f"Image: {Path(row['image_path']).name}")
    print(f"  bbox_x: {row['bbox_x']}")
    print(f"  bbox_y: {row['bbox_y']}")
    print(f"  bbox_width: {row['bbox_width']}")
    print(f"  bbox_height: {row['bbox_height']}")
    print()

conn.close()
