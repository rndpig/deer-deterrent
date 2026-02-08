#!/usr/bin/env python3
"""Find duplicate snapshot files and report summary only."""
import sqlite3
import hashlib
import os

DB_PATH = "/home/rndpig/deer-deterrent/backend/data/training.db"
BASE = "/home/rndpig/deer-deterrent/backend"

db = sqlite3.connect(DB_PATH)
cur = db.cursor()
cur.execute("""
    SELECT id, snapshot_path, deer_detected, detection_confidence, model_version, created_at
    FROM ring_events 
    WHERE snapshot_path IS NOT NULL AND snapshot_path != ''
    ORDER BY id
""")
rows = cur.fetchall()

hashes = {}
missing = []
for eid, snap, deer, conf, model, created in rows:
    full = os.path.join(BASE, snap) if not snap.startswith("/") else snap
    if os.path.exists(full):
        h = hashlib.md5(open(full, "rb").read()).hexdigest()
        hashes.setdefault(h, []).append((eid, snap, deer, conf, model, created, full))
    else:
        missing.append((eid, snap, deer, conf))

dupes = {h: evts for h, evts in hashes.items() if len(evts) > 1}
print(f"Total snapshots in DB: {len(rows)}")
print(f"Found on disk: {len(rows) - len(missing)}")
print(f"Missing from disk: {len(missing)}")
print(f"Unique file hashes: {len(hashes)}")
print(f"Duplicate groups: {len(dupes)}")
total_dupes = sum(len(evts) - 1 for evts in dupes.values())
print(f"Total duplicate files to remove: {total_dupes}")

for h, evts in sorted(dupes.items(), key=lambda x: -len(x[1])):
    print(f"\n=== Hash {h} ({len(evts)} copies) ===")
    for eid, snap, deer, conf, model, created, full in evts:
        size = os.path.getsize(full)
        print(f"  Event {eid}: deer={deer} conf={conf} created={created} size={size} path={snap}")

if missing:
    print(f"\n=== Missing files: {len(missing)} (first 10) ===")
    for eid, snap, deer, conf in missing[:10]:
        print(f"  Event {eid}: deer={deer} conf={conf} path={snap}")

db.close()
