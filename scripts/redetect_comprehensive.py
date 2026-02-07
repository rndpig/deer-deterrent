#!/usr/bin/env python3
"""Comprehensive re-detection: run YOLO26s directly on all deer snapshots + recent snapshots.
Bypasses the API threshold to show raw detections."""
import sqlite3
import json
import os
import sys
import numpy as np
from pathlib import Path

# Direct model loading for threshold-free detection
from ultralytics import YOLO
import cv2

DB_PATH = '/home/rndpig/deer-deterrent/backend/data/training.db'
MODEL_PATH = '/home/rndpig/deer-deterrent/dell-deployment/models/production/best.pt'
CLAHE_CLIP = 3.0
CLAHE_TILE = (8, 8)

SNAPSHOT_PREFIXES = [
    '/home/rndpig/deer-deterrent/backend/',
    '/home/rndpig/deer-deterrent/backend/data/',
    '/home/rndpig/deer-deterrent/',
    '',
]

def find_snapshot(path):
    if not path:
        return None
    for prefix in SNAPSHOT_PREFIXES:
        full = prefix + path
        if os.path.exists(full):
            return full
    return None

def apply_clahe(img):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=CLAHE_TILE)
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

def detect(model, filepath, conf_threshold=0.1):
    """Run detection with CLAHE and low threshold to see all candidates."""
    img = cv2.imread(filepath)
    if img is None:
        return None, 'failed to read'
    h, w = img.shape[:2]
    img_clahe = apply_clahe(img)
    results = model.predict(img_clahe, conf=conf_threshold, verbose=False)
    dets = []
    for r in results:
        for box in r.boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            dets.append({
                'x1': round(x1, 1), 'y1': round(y1, 1),
                'x2': round(x2, 1), 'y2': round(y2, 1),
                'conf': round(conf, 4), 'cls': cls,
                'w_pct': round((x2-x1)/w*100, 1),
                'h_pct': round((y2-y1)/h*100, 1),
            })
    dets.sort(key=lambda d: d['conf'], reverse=True)
    return dets, '%dx%d' % (w, h)

# Load model
print('Loading model: %s' % MODEL_PATH)
model = YOLO(MODEL_PATH)
import hashlib
md5 = hashlib.md5(open(MODEL_PATH, 'rb').read()).hexdigest()
print('Model MD5: %s' % md5)
print('Model arch: %s' % model.model.yaml.get('yaml_file', 'unknown'))
print()

db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
cur = db.cursor()

# === Part 1: Re-detect all deer=1 ring events ===
print('=' * 70)
print('PART 1: RE-DETECTION OF RING EVENTS WITH deer_detected=1')
print('=' * 70)
cur.execute('SELECT id, camera_id, detection_confidence, detection_bboxes, snapshot_path FROM ring_events WHERE deer_detected=1 ORDER BY id')
events = cur.fetchall()
print('Events: %d' % len(events))
print()

for e in events:
    eid = e['id']
    snap = e['snapshot_path']
    old_conf = e['detection_confidence'] or 0
    old_bboxes = e['detection_bboxes']
    old_count = 0
    if old_bboxes:
        try:
            parsed = json.loads(old_bboxes)
            if isinstance(parsed, list):
                old_count = len(parsed)
        except:
            pass

    real_path = find_snapshot(snap)
    if not real_path:
        print('Event %d: MISSING (%s) old_conf=%.3f old_deer=%d' % (eid, snap, old_conf, old_count))
        continue

    dets, img_info = detect(model, real_path)
    if dets is None:
        print('Event %d: READ ERROR (%s)' % (eid, real_path))
        continue

    above_60 = [d for d in dets if d['conf'] >= 0.6]
    above_30 = [d for d in dets if d['conf'] >= 0.3]
    above_10 = [d for d in dets if d['conf'] >= 0.1]

    print('Event %d [%s]: OLD(conf=%.3f, deer=%d) -> NEW(>=0.6: %d, >=0.3: %d, >=0.1: %d)' % (
        eid, img_info, old_conf, old_count, len(above_60), len(above_30), len(above_10)))
    for d in dets:
        marker = ' ***' if d['conf'] >= 0.6 else (' *' if d['conf'] >= 0.3 else '')
        print('  conf=%.4f bbox=(%.0f,%.0f)-(%.0f,%.0f) size=%.1f%%x%.1f%%%s' % (
            d['conf'], d['x1'], d['y1'], d['x2'], d['y2'], d['w_pct'], d['h_pct'], marker))

# === Part 2: Run on recent periodic snapshots ===
print()
print('=' * 70)
print('PART 2: DETECTION ON RECENT PERIODIC SNAPSHOTS')
print('=' * 70)
snap_dir = '/home/rndpig/deer-deterrent/backend/data/snapshots/'
if os.path.isdir(snap_dir):
    snaps = sorted([f for f in os.listdir(snap_dir) if f.endswith('.jpg')])
    print('Total snapshot files: %d' % len(snaps))
    # Run on the most recent 20
    recent = snaps[-20:]
    print('Testing most recent %d snapshots' % len(recent))
    print()
    for fname in recent:
        fpath = os.path.join(snap_dir, fname)
        dets, img_info = detect(model, fpath)
        if dets is None:
            continue
        above_60 = [d for d in dets if d['conf'] >= 0.6]
        if above_60:
            print('%s [%s]: %d DEER DETECTED (>=0.6)' % (fname, img_info, len(above_60)))
            for d in above_60:
                print('  conf=%.4f bbox=(%.0f,%.0f)-(%.0f,%.0f)' % (
                    d['conf'], d['x1'], d['y1'], d['x2'], d['y2']))
        else:
            all_dets = [d for d in dets if d['conf'] >= 0.1]
            if all_dets:
                print('%s [%s]: no deer (best conf=%.4f)' % (fname, img_info, all_dets[0]['conf']))
            else:
                print('%s [%s]: no detections' % (fname, img_info))

db.close()
print()
print('Done.')
