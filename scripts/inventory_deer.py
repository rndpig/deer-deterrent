#!/usr/bin/env python3
"""Inventory all deer detections in the database."""
import sqlite3, json, os

db = sqlite3.connect('/home/rndpig/deer-deterrent/backend/data/training.db')
db.row_factory = sqlite3.Row

# Ring events with deer
cur = db.cursor()
cur.execute('SELECT id, camera_id, detection_confidence, detection_bboxes, snapshot_path, created_at FROM ring_events WHERE deer_detected=1 ORDER BY id')
events = cur.fetchall()
print('=== RING EVENTS WITH deer_detected=1 ===')
print('Count: %d' % len(events))
for e in events:
    snap = e['snapshot_path']
    paths_to_check = []
    if snap:
        paths_to_check.append(snap)
        paths_to_check.append('/home/rndpig/deer-deterrent/backend/data/' + snap)
        paths_to_check.append('/home/rndpig/deer-deterrent/' + snap)

    exists = False
    real_path = None
    for p in paths_to_check:
        if os.path.exists(p):
            exists = True
            real_path = p
            break

    bboxes = e['detection_bboxes']
    n_deer = 0
    if bboxes:
        try:
            parsed = json.loads(bboxes)
            if isinstance(parsed, list):
                n_deer = len(parsed)
        except:
            pass

    print('  ID=%s cam=%s conf=%s deer=%d exists=%s path=%s' % (
        e['id'], str(e['camera_id'])[:8], e['detection_confidence'], n_deer, exists, snap))
    if real_path:
        print('    -> %s (%dKB)' % (real_path, os.path.getsize(real_path)//1024))

# Detections table
cur.execute('SELECT COUNT(*) as cnt FROM detections')
print('\n=== DETECTIONS TABLE ===')
print('Total: %d' % cur.fetchone()['cnt'])
cur.execute('SELECT id, snapshot_id, camera_id, confidence, deer_count, created_at FROM detections ORDER BY created_at DESC LIMIT 15')
for d in cur.fetchall():
    cam = str(d['camera_id'])[:8] if d['camera_id'] else 'N/A'
    print('  det=%s snap=%s cam=%s conf=%s deer=%s time=%s' % (
        d['id'], d['snapshot_id'], cam, d['confidence'], d['deer_count'], d['created_at']))

# Snapshots with deer
cur.execute('SELECT COUNT(*) as cnt FROM snapshots WHERE deer_detected=1')
deer_snaps = cur.fetchone()['cnt']
cur.execute('SELECT COUNT(*) as cnt FROM snapshots')
total_snaps = cur.fetchone()['cnt']
print('\n=== SNAPSHOTS TABLE ===')
print('Total: %d, Deer: %d' % (total_snaps, deer_snaps))
if deer_snaps > 0:
    cur.execute('SELECT id, camera_id, detection_confidence, snapshot_path, created_at FROM snapshots WHERE deer_detected=1 ORDER BY created_at DESC LIMIT 15')
    for s in cur.fetchall():
        snap = s['snapshot_path']
        exists = False
        if snap:
            for prefix in ['', '/home/rndpig/deer-deterrent/backend/data/', '/home/rndpig/deer-deterrent/']:
                if os.path.exists(prefix + snap):
                    exists = True
                    break
        cam = str(s['camera_id'])[:8] if s['camera_id'] else 'N/A'
        print('  id=%s cam=%s conf=%s exists=%s path=%s time=%s' % (
            s['id'], cam, s['detection_confidence'], exists, snap, s['created_at']))

db.close()
