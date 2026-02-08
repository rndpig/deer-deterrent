#!/usr/bin/env python3
"""Investigate missing snapshot files."""
import sqlite3, os, collections, datetime

DB = '/home/rndpig/deer-deterrent/backend/data/training.db'
BASE = '/home/rndpig/deer-deterrent/backend'

db = sqlite3.connect(DB)
cur = db.cursor()

cur.execute("""SELECT id, snapshot_path, deer_detected, created_at, camera_id 
               FROM ring_events WHERE snapshot_path IS NOT NULL AND snapshot_path != '' 
               ORDER BY id""")
rows = cur.fetchall()

found = []
missing = []

for eid, snap, deer, created, cam in rows:
    candidates = [
        os.path.join(BASE, snap),
        os.path.join(BASE, 'data', snap) if not snap.startswith('data/') else None,
    ]
    candidates = [c for c in candidates if c]
    
    exists = any(os.path.exists(c) for c in candidates)
    
    pat = 'data/snapshots/*' if snap.startswith('data/snapshots/') else ('snapshots/*' if snap.startswith('snapshots/') else 'other')
    
    if exists:
        found.append((eid, snap, deer, created, cam, pat))
    else:
        missing.append((eid, snap, deer, created, cam, pat))

print(f'Total events with snapshot_path: {len(rows)}')
print(f'Found on disk: {len(found)}')
print(f'Missing from disk: {len(missing)}')

# Path pattern breakdown
path_counts = collections.Counter()
for r in found:
    path_counts[('found', r[5])] += 1
for r in missing:
    path_counts[('missing', r[5])] += 1

print('\n=== Path patterns ===')
for pat in ['snapshots/*', 'data/snapshots/*', 'other']:
    fc = path_counts.get(('found', pat), 0)
    mc = path_counts.get(('missing', pat), 0)
    if fc + mc > 0:
        print(f'  {pat}: {fc} found, {mc} missing')

# Check actual files on disk
print('\n=== Files on disk ===')
for d in [os.path.join(BASE, 'snapshots'), os.path.join(BASE, 'data', 'snapshots')]:
    if os.path.exists(d):
        files = os.listdir(d)
        print(f'{d}: {len(files)} files')
        full = [(f, os.path.getmtime(os.path.join(d, f))) for f in files]
        full.sort(key=lambda x: -x[1])
        if full:
            print(f'  Newest: {full[0][0]} ({datetime.datetime.fromtimestamp(full[0][1])})')
            print(f'  Oldest: {full[-1][0]} ({datetime.datetime.fromtimestamp(full[-1][1])})')
    else:
        print(f'{d}: DOES NOT EXIST')

# Missing breakdown
missing_event = [m for m in missing if 'event_' in m[1]]
missing_periodic = [m for m in missing if 'periodic_' in m[1]]
print(f'\nMissing: {len(missing_event)} event snapshots, {len(missing_periodic)} periodic snapshots')

if missing:
    dates = sorted([m[3] for m in missing if m[3]])
    if dates:
        print(f'Missing date range: {dates[0]} to {dates[-1]}')
if found:
    dates = sorted([f[3] for f in found if f[3]])
    if dates:
        print(f'Found date range: {dates[0]} to {dates[-1]}')

# Recent events - pipeline health
print('\n=== Recent events (last 24h) ===')
cur.execute("""SELECT id, snapshot_path, deer_detected, created_at, camera_id
               FROM ring_events 
               WHERE created_at > datetime('now', '-24 hours')
               ORDER BY created_at DESC LIMIT 15""")
for eid, snap, deer, created, cam in cur.fetchall():
    has_file = 'no_path'
    if snap:
        full = os.path.join(BASE, snap) if not snap.startswith('/') else snap
        if not os.path.exists(full) and not snap.startswith('data/'):
            full = os.path.join(BASE, 'data', snap)
        has_file = 'EXISTS' if os.path.exists(full) else 'MISSING'
    print(f'  {eid}: {created} cam={cam[:8]}.. deer={deer} file={has_file} path={snap}')

# Total ring events without snapshots
cur.execute("SELECT COUNT(*) FROM ring_events WHERE snapshot_path IS NULL OR snapshot_path = ''")
no_snap = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM ring_events")
total = cur.fetchone()[0]
print(f'\n=== Overall ===')
print(f'Total ring events: {total}')
print(f'Events with snapshot path: {len(rows)}')
print(f'Events without snapshot path: {no_snap}')

db.close()
