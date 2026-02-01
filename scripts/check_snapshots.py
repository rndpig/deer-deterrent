import requests

r = requests.get('http://192.168.7.215:8000/api/ring-snapshots', params={'with_deer': True, 'limit': 100})
data = r.json()
print(f"Total deer snapshots: {len(data['snapshots'])}")
with_bbox = sum(1 for s in data['snapshots'] if s.get('detection_bboxes'))
print(f"With bbox data: {with_bbox}")
print(f"\nDeer snapshot IDs: {[s['id'] for s in data['snapshots']]}")
