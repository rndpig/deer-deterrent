#!/usr/bin/env python3
"""
Seed default property map overlays from existing camera_zones settings.

Run once after first deploy:
  python3 scripts/seed_property_overlays.py

Idempotent — overwrites whatever is currently stored.
Note: If camera_zones in settings drifts from the overlay JSON, re-run this script.
"""
import json
import sys
import os
from pathlib import Path
from datetime import datetime
import sqlite3

# Known camera ring-mqtt IDs -> position/orientation (approximate normalized coords)
# Based on property layout: East=right, West=left, North=top, South=bottom
CAMERA_DEFAULTS = {
    '10cea9e4511f': {
        'id': 'cam-woods',
        'label': 'Woods',
        'x': 0.22, 'y': 0.52,
        'rotation_deg': 90,   # facing east (back toward house)
        'fov_deg': 100,
        'range': 0.18,
        'color': '#f59e0b',
    },
    'c4dbad08f862': {
        'id': 'cam-side',
        'label': 'Side',
        'x': 0.74, 'y': 0.28,
        'rotation_deg': 0,    # facing north
        'fov_deg': 110,
        'range': 0.16,
        'color': '#3b82f6',
    },
    '587a624d3fae': {
        'id': 'cam-driveway',
        'label': 'Driveway',
        'x': 0.82, 'y': 0.22,
        'rotation_deg': 60,   # facing east-northeast
        'fov_deg': 100,
        'range': 0.16,
        'color': '#10b981',
    },
    '4439c4de7a79': {
        'id': 'cam-frontdoor',
        'label': 'Front Door',
        'x': 0.80, 'y': 0.42,
        'rotation_deg': 110,  # facing east-southeast
        'fov_deg': 90,
        'range': 0.12,
        'color': '#8b5cf6',
    },
    'f045dae9383a': {
        'id': 'cam-back',
        'label': 'Back',
        'x': 0.72, 'y': 0.52,
        'rotation_deg': 225,  # facing west-southwest
        'fov_deg': 100,
        'range': 0.18,
        'color': '#ec4899',
    },
}

# Zone placeholder polygons (small triangles/quads around approximate area)
ZONE_DEFAULTS = {
    1: {
        'id': 'zone-1',
        'label': 'Driveway North',
        'color': '#10b981',
        'fill_opacity': 0.35,
        'stroke_width': 2,
        'polygon': [[0.78, 0.15], [0.88, 0.15], [0.83, 0.28]],
        'meta': {'rainbird_zone': 1},
    },
    2: {
        'id': 'zone-2',
        'label': 'Garage North',
        'color': '#4ade80',
        'fill_opacity': 0.35,
        'stroke_width': 2,
        'polygon': [[0.65, 0.14], [0.76, 0.14], [0.70, 0.28]],
        'meta': {'rainbird_zone': 2},
    },
    5: {
        'id': 'zone-5',
        'label': 'Woods North',
        'color': '#22d3ee',
        'fill_opacity': 0.30,
        'stroke_width': 2,
        'polygon': [[0.05, 0.10], [0.40, 0.10], [0.40, 0.40], [0.05, 0.40]],
        'meta': {'rainbird_zone': 5},
    },
}

SENSOR_DEFAULTS = [
    {
        'id': 'soil-1',
        'type': 'marker',
        'label': 'Soil Zone 1',
        'x': 0.70, 'y': 0.35,
        'color': '#06b6d4',
        'meta': {'channel': 1, 'kind': 'soil_moisture'},
    },
    {
        'id': 'light-1',
        'type': 'marker',
        'label': 'Light sensor',
        'x': 0.65, 'y': 0.60,
        'color': '#fbbf24',
        'meta': {'name': 'outdoor', 'kind': 'light'},
    },
]

LABEL_DEFAULTS = [
    {'id': 'lbl-house',   'type': 'label', 'label': 'House',        'x': 0.82, 'y': 0.50, 'meta': {}},
    {'id': 'lbl-woods',   'type': 'label', 'label': 'Woods',        'x': 0.15, 'y': 0.60, 'meta': {}},
    {'id': 'lbl-street',  'type': 'label', 'label': 'Briarwood Ln', 'x': 0.78, 'y': 0.08, 'meta': {}},
]


def fetch_settings_from_db(db_path):
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT settings_json FROM system_settings WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return json.loads(row['settings_json'])
    except Exception as e:
        print(f'Warning: could not read settings from DB: {e}')
    return {}


def build_overlay(settings):
    camera_zones = settings.get('camera_zones', {})

    # Build camera items — include all known cameras
    camera_items = []
    for ring_id, defaults in CAMERA_DEFAULTS.items():
        item = {
            'id': defaults['id'],
            'type': 'camera',
            'label': defaults['label'],
            'x': defaults['x'],
            'y': defaults['y'],
            'rotation_deg': defaults['rotation_deg'],
            'fov_deg': defaults['fov_deg'],
            'range': defaults['range'],
            'color': defaults['color'],
            'meta': {'ring_camera_id': ring_id},
        }
        camera_items.append(item)

    # Build zone items — include zones referenced by camera_zones setting + always zones 1,2,5
    used_zone_nums = set([1, 2, 5])
    for zones in camera_zones.values():
        if isinstance(zones, list):
            used_zone_nums.update(zones)
        elif isinstance(zones, int):
            used_zone_nums.add(zones)

    zone_items = []
    for znum in sorted(used_zone_nums):
        if znum in ZONE_DEFAULTS:
            zone_items.append(dict(ZONE_DEFAULTS[znum], type='polygon'))
        else:
            zone_items.append({
                'id': f'zone-{znum}',
                'type': 'polygon',
                'label': f'Zone {znum}',
                'color': '#94a3b8',
                'fill_opacity': 0.30,
                'stroke_width': 2,
                'polygon': [[0.45, 0.45], [0.55, 0.45], [0.50, 0.55]],
                'meta': {'rainbird_zone': znum},
            })

    overlay = {
        'schema_version': 1,
        'updated_at': None,
        'image': {
            'url': '/api/property-map/image',
            'intrinsic_width': 1782,
            'intrinsic_height': 768,
        },
        'layers': [
            {
                'id': 'cameras',
                'name': 'Cameras',
                'icon': 'camera',
                'default_visible_in': ['deer'],
                'items': camera_items,
            },
            {
                'id': 'zones',
                'name': 'Irrigation Zones',
                'icon': 'droplet-fill',
                'default_visible_in': ['deer'],
                'items': zone_items,
            },
            {
                'id': 'sensors',
                'name': 'Sensors',
                'icon': 'droplet',
                'default_visible_in': ['weather'],
                'items': SENSOR_DEFAULTS,
            },
            {
                'id': 'labels',
                'name': 'Labels',
                'icon': 'type',
                'default_visible_in': ['deer', 'weather'],
                'items': LABEL_DEFAULTS,
            },
        ],
    }
    return overlay


def main():
    db_path = Path(__file__).parent.parent / 'backend' / 'data' / 'training.db'
    if not db_path.exists():
        print(f'ERROR: DB not found at {db_path}')
        sys.exit(1)

    print(f'Reading settings from {db_path}…')
    settings = fetch_settings_from_db(str(db_path))
    print(f'camera_zones: {settings.get("camera_zones", {})}')

    overlay = build_overlay(settings)

    total_items = sum(len(l['items']) for l in overlay['layers'])
    print(f'Built overlay: {len(overlay["layers"])} layers, {total_items} items')

    data_json = json.dumps(overlay)
    updated_at = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS property_overlay (
            id         INTEGER PRIMARY KEY CHECK (id = 1),
            data_json  TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            updated_by TEXT
        )
    """)
    conn.execute("""
        INSERT INTO property_overlay (id, data_json, updated_at, updated_by)
        VALUES (1, ?, ?, 'seed_script')
        ON CONFLICT(id) DO UPDATE SET
            data_json  = excluded.data_json,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
    """, (data_json, updated_at))
    conn.commit()
    conn.close()

    print(f'Overlay seeded at {db_path}')
    print(f'  Cameras: {len(overlay["layers"][0]["items"])}')
    print(f'  Zones:   {len(overlay["layers"][1]["items"])}')
    print(f'  Sensors: {len(overlay["layers"][2]["items"])}')
    print(f'  Labels:  {len(overlay["layers"][3]["items"])}')


if __name__ == '__main__':
    main()
