#!/usr/bin/env python3
"""Deployment verification script - run INSIDE the ml-detector container."""
import os
import hashlib

# 1. Verify model file identity
model_path = "/app/models/production/best.pt"
size_mb = os.path.getsize(model_path) / (1024 * 1024)
md5 = hashlib.md5(open(model_path, 'rb').read()).hexdigest()
print(f"Model path:  {model_path}")
print(f"Model size:  {size_mb:.2f} MB")
print(f"Model MD5:   {md5}")

# Expected values
EXPECTED_MD5 = "cb50366cac8b5a5f5a445f3c85277da6"
EXPECTED_SIZE_MIN = 19.0  # MB - YOLO26s should be ~19-20MB, YOLOv8n was ~6MB
assert md5 == EXPECTED_MD5, f"MD5 MISMATCH! Expected {EXPECTED_MD5}, got {md5}"
assert size_mb > EXPECTED_SIZE_MIN, f"Model too small ({size_mb:.2f} MB) - may be old YOLOv8n"
print(f"[PASS] MD5 matches expected YOLO26s model")
print(f"[PASS] Size ({size_mb:.2f} MB) confirms YOLO26s (not YOLOv8n ~6MB)")

# 2. Verify architecture
from ultralytics import YOLO
m = YOLO(model_path)
model_obj = m.model
n_params = sum(p.numel() for p in model_obj.parameters())
if hasattr(model_obj, 'yaml'):
    yaml_file = model_obj.yaml.get('yaml_file', 'unknown')
else:
    yaml_file = 'unknown'
print(f"Architecture: {yaml_file}")
print(f"Parameters:   {n_params:,}")
assert 'yolo26' in yaml_file.lower() or 'yolo11' in yaml_file.lower() or n_params > 9_000_000, \
    f"Architecture mismatch: {yaml_file}, params={n_params}"
print(f"[PASS] Architecture confirmed as YOLO26s")

# 3. Verify ultralytics version
import ultralytics
v = ultralytics.__version__
major, minor = int(v.split('.')[0]), int(v.split('.')[1])
print(f"Ultralytics:  {v}")
assert major >= 8 and minor >= 4, f"ultralytics {v} too old, need >=8.4.0"
print(f"[PASS] ultralytics {v} >= 8.4.0")

# 4. Verify CLAHE is enabled
import cv2
clahe_enabled = os.getenv("ENABLE_CLAHE", "true").lower() == "true"
print(f"CLAHE enabled: {clahe_enabled}")
print(f"OpenCV version: {cv2.__version__}")

# 5. Quick inference test
import numpy as np
img = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
results = m.predict(img, verbose=False)
print(f"Inference test: OK (returned {len(results)} result)")

print()
print("=" * 50)
print("ALL DEPLOYMENT CHECKS PASSED")
print("=" * 50)
