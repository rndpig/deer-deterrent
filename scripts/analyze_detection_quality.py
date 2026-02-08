#!/usr/bin/env python3
"""Analyze deer detection quality - check bbox counts and confidence."""
import sqlite3
import json

DB = '/home/rndpig/deer-deterrent/backend/data/training.db'
db = sqlite3.connect(DB)
cur = db.cursor()

# Recent deer events
cur.execute("""SELECT id, camera_id, deer_detected, detection_confidence, 
               detection_bboxes, model_version, created_at 
               FROM ring_events WHERE deer_detected=1 ORDER BY id DESC LIMIT 10""")

print("=== Recent Deer Events ===")
for row in cur.fetchall():
    eid, cam, deer, conf, bboxes_str, model, created = row
    num_boxes = 0
    if bboxes_str:
        try:
            bboxes = json.loads(bboxes_str)
            num_boxes = len(bboxes)
        except:
            num_boxes = -1
    print(f"Event {eid}: cam={cam[:8]}.. conf={conf} boxes={num_boxes} model={model} created={created}")
    if bboxes_str:
        try:
            bboxes = json.loads(bboxes_str)
            for b in bboxes:
                print(f"  bbox: conf={b.get('confidence', '?')} x1={b.get('x1', b.get('bbox', {}).get('x1', '?'))}")
        except:
            print(f"  raw: {bboxes_str[:200]}")

# Check all detection counts
print("\n=== Detection Count Distribution ===")
cur.execute("""SELECT detection_bboxes FROM ring_events WHERE deer_detected=1 AND detection_bboxes IS NOT NULL""")
counts = {}
for (bboxes_str,) in cur.fetchall():
    try:
        bboxes = json.loads(bboxes_str)
        n = len(bboxes)
        counts[n] = counts.get(n, 0) + 1
    except:
        counts[-1] = counts.get(-1, 0) + 1

for n in sorted(counts.keys()):
    print(f"  {n} deer detected: {counts[n]} events")

# All recent events (not just deer) from active hours
print("\n=== Last 20 events within active hours ===")
cur.execute("""SELECT id, camera_id, deer_detected, detection_confidence, 
               event_type, created_at 
               FROM ring_events ORDER BY id DESC LIMIT 20""")
for row in cur.fetchall():
    eid, cam, deer, conf, etype, created = row
    print(f"  {eid}: cam={cam[:8]}.. deer={deer} conf={conf} type={etype} {created}")

db.close()
