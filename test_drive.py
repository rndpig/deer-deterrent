#!/usr/bin/env python3
from pathlib import Path
import json

credentials_path = '/home/rndpig/deer-deterrent/configs/google-credentials.json'
p = Path(credentials_path)

print(f"Checking: {credentials_path}")
print(f"Exists: {p.exists()}")
print(f"Is file: {p.is_file()}")
print(f"Readable: {p.stat().st_mode if p.exists() else 'N/A'}")

if p.exists():
    try:
        with open(p) as f:
            data = json.load(f)
        print(f"Valid JSON: Yes")
        print(f"Type: {data.get('type', 'unknown')}")
    except Exception as e:
        print(f"Error reading: {e}")
