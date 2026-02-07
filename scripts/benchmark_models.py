#!/usr/bin/env python3
"""Compare model architectures and benchmark inference speed."""
import os
import time
import hashlib
import numpy as np
from ultralytics import YOLO

models = {
    "Production YOLOv8n": "/home/rndpig/deer-deterrent/dell-deployment/models/production/best.pt",
    "New YOLO26s": "/home/rndpig/deer-deterrent/runs/train/deer_v2_20260206_2011_phase2/weights/best.pt",
}

# Phase 1
phase1_path = "/home/rndpig/deer-deterrent/runs/train/deer_v2_20260206_2011_phase12/weights/best.pt"
if os.path.exists(phase1_path):
    models["YOLO26s Phase1"] = phase1_path

print("=" * 80)
print("MODEL ARCHITECTURE & PERFORMANCE COMPARISON")
print("=" * 80)

# Create a dummy image for benchmarking
dummy_img = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

for name, path in models.items():
    print(f"\n{'─' * 60}")
    print(f"  {name}")
    print(f"{'─' * 60}")
    size_mb = os.path.getsize(path) / (1024 * 1024)
    md5 = hashlib.md5(open(path, 'rb').read()).hexdigest()

    m = YOLO(path)

    # Get model info via the model attribute
    try:
        model_obj = m.model
        n_params = sum(p.numel() for p in model_obj.parameters())
        n_layers = len(list(model_obj.modules()))
        if hasattr(model_obj, 'yaml'):
            yaml_file = model_obj.yaml.get('yaml_file', 'unknown')
            scale = model_obj.yaml.get('scale', 'unknown')
        else:
            yaml_file = 'unknown'
            scale = 'unknown'
    except Exception as e:
        n_params = 0
        n_layers = 0
        yaml_file = f'error: {e}'
        scale = 'unknown'

    # Warmup
    m.predict(dummy_img, verbose=False)

    # Benchmark: 10 inferences
    times = []
    for _ in range(10):
        t0 = time.time()
        m.predict(dummy_img, verbose=False)
        times.append((time.time() - t0) * 1000)

    avg_ms = sum(times) / len(times)
    min_ms = min(times)
    max_ms = max(times)

    print(f"  File size:       {size_mb:.2f} MB")
    print(f"  MD5:             {md5}")
    print(f"  Architecture:    {yaml_file}")
    print(f"  Scale:           {scale}")
    print(f"  Modules:         {n_layers}")
    print(f"  Parameters:      {n_params:,}")
    print(f"  Inference (avg): {avg_ms:.1f} ms  (min={min_ms:.1f}, max={max_ms:.1f})")
    print(f"  Throughput:      {1000/avg_ms:.1f} FPS")

print(f"\n{'=' * 80}")
print("NOTES:")
print("  - 'Production YOLOv8n' was labeled 'YOLO26n v1.1' but is actually YOLOv8n")
print("  - 'New YOLO26s' is a real YOLO v11/26 small architecture")
print("  - Inference benchmarked on i7-4790 CPU (3.60 GHz) with 640x640 images")
print(f"{'=' * 80}")
