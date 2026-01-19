#!/usr/bin/env python3
"""Fix camera name for video 32"""

import sqlite3

conn = sqlite3.connect('data/training.db')
cursor = conn.cursor()

# Update video 32 to have correct camera name
cursor.execute(
    "UPDATE videos SET camera = ?, camera_name = ? WHERE id = ?",
    ('side', 'Side', 32)
)

# Verify the update
cursor.execute("SELECT id, filename, camera, camera_name FROM videos WHERE id = 32")
result = cursor.fetchone()

conn.commit()
conn.close()

print(f"Updated video 32:")
print(f"  ID: {result[0]}")
print(f"  Filename: {result[1]}")
print(f"  Camera: {result[2]}")
print(f"  Camera Name: {result[3]}")
