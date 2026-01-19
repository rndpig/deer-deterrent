import requests
import json

response = requests.get('https://deer-api.rndpig.com/api/videos')
videos = response.json()

print(f"Total videos: {len(videos)}")
print()

for v in videos[:3]:
    print(f"Video {v['id']}: {v['filename']}")
    print(f"  Frames: {v['frame_count']}")
    print(f"  Detections: {v['detection_count']}")
    print(f"  Annotations: {v['annotation_count']}")
    print(f"  Uploaded: {v['upload_date'][:19]}")
    print()
