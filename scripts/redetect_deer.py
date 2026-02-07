#!/usr/bin/env python3
"""Re-run detection on all deer snapshots using the new YOLO26s model via the ml-detector API."""
import sqlite3
import json
import os
import sys
import requests
import time

DB_PATH = '/home/rndpig/deer-deterrent/backend/data/training.db'
ML_DETECTOR_URL = 'http://localhost:8001/detect'
SNAPSHOT_PREFIXES = [
    '/home/rndpig/deer-deterrent/backend/',   # data/snapshots/... -> backend/data/snapshots/...
    '/home/rndpig/deer-deterrent/backend/data/',  # snapshots/... -> backend/data/snapshots/...
    '/home/rndpig/deer-deterrent/',
    '/app/data/',
    '',
]

def find_snapshot(path):
    """Try to find the actual file on disk."""
    if not path:
        return None
    for prefix in SNAPSHOT_PREFIXES:
        full = prefix + path
        if os.path.exists(full):
            return full
    return None

def detect_image(filepath):
    """Send image to ml-detector API and get results."""
    with open(filepath, 'rb') as f:
        files = {'file': (os.path.basename(filepath), f, 'image/jpeg')}
        resp = requests.post(ML_DETECTOR_URL, files=files, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    else:
        return {'error': resp.status_code, 'text': resp.text[:200]}

# Connect to DB
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
cur = db.cursor()

# Get all ring events with deer_detected=1
cur.execute('SELECT id, camera_id, detection_confidence, detection_bboxes, snapshot_path FROM ring_events WHERE deer_detected=1 ORDER BY id')
events = cur.fetchall()

print('=' * 70)
print('RE-DETECTION OF ALL DEER SNAPSHOTS WITH NEW YOLO26s MODEL')
print('=' * 70)
print('Events with deer_detected=1: %d' % len(events))
print()

results = []
for e in events:
    eid = e['id']
    cam = e['camera_id'][:12]
    old_conf = e['detection_confidence']
    snap_path = e['snapshot_path']
    
    # Parse old bbox count
    old_bboxes = e['detection_bboxes']
    old_count = 0
    if old_bboxes:
        try:
            parsed = json.loads(old_bboxes)
            if isinstance(parsed, list):
                old_count = len(parsed)
        except:
            pass
    
    # Find file
    real_path = find_snapshot(snap_path)
    
    if not real_path:
        print('[SKIP] Event %d: snapshot not found on disk (%s)' % (eid, snap_path))
        results.append({
            'id': eid, 'status': 'missing',
            'old_conf': old_conf, 'old_count': old_count,
            'new_conf': None, 'new_count': None
        })
        continue
    
    # Run detection
    det = detect_image(real_path)
    
    if 'error' in det:
        print('[ERROR] Event %d: API error %s' % (eid, det))
        results.append({
            'id': eid, 'status': 'error',
            'old_conf': old_conf, 'old_count': old_count,
            'new_conf': None, 'new_count': None
        })
        continue
    
    new_detections = det.get('detections', [])
    new_count = len(new_detections)
    new_conf = max([d.get('confidence', 0) for d in new_detections]) if new_detections else 0
    
    change = ''
    if new_count > old_count:
        change = ' [+%d MORE DEER]' % (new_count - old_count)
    elif new_count < old_count:
        change = ' [-%d FEWER]' % (old_count - new_count)
    
    print('Event %d: OLD(conf=%.3f, deer=%d) -> NEW(conf=%.3f, deer=%d)%s' % (
        eid, old_conf or 0, old_count, new_conf, new_count, change))
    for d in new_detections:
        print('  bbox: x1=%.1f y1=%.1f x2=%.1f y2=%.1f conf=%.3f' % (
            d.get('x1',0), d.get('y1',0), d.get('x2',0), d.get('y2',0), d.get('confidence',0)))
    
    results.append({
        'id': eid, 'status': 'ok',
        'old_conf': old_conf, 'old_count': old_count,
        'new_conf': new_conf, 'new_count': new_count,
        'detections': new_detections
    })

# Summary
print()
print('=' * 70)
print('SUMMARY')
print('=' * 70)
ok = [r for r in results if r['status'] == 'ok']
missing = [r for r in results if r['status'] == 'missing']
errors = [r for r in results if r['status'] == 'error']
print('Processed: %d, Missing snapshots: %d, Errors: %d' % (len(ok), len(missing), len(errors)))
if ok:
    total_old = sum(r['old_count'] for r in ok)
    total_new = sum(r['new_count'] for r in ok)
    print('Total deer (old model): %d' % total_old)
    print('Total deer (new YOLO26s): %d' % total_new)
    avg_old = sum(r['old_conf'] or 0 for r in ok) / len(ok)
    avg_new = sum(r['new_conf'] or 0 for r in ok) / len(ok)
    print('Avg confidence (old): %.3f' % avg_old)
    print('Avg confidence (new): %.3f' % avg_new)

db.close()
