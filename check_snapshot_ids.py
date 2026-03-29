import json
import sys

with open('/tmp/snapshots.json') as f:
    data = json.load(f)

target_ids = ['53720', '53721', '53722', '53723', '53724', '56646']
matches = [s for s in data['snapshots'] if str(s['id']) in target_ids]

for m in sorted(matches, key=lambda x: str(x['id'])):
    print(f"{m['id']}: {m.get('snapshot_path', 'NO PATH')}")
