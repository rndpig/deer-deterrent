#!/usr/bin/env python3
"""Compare all models for deployment decision."""
import os
import json
from ultralytics import YOLO

models = {
    "Production (current)": "/home/rndpig/deer-deterrent/dell-deployment/models/production/best.pt",
    "New YOLO26s (Phase 2 best)": "/home/rndpig/deer-deterrent/runs/train/deer_v2_20260206_2011_phase2/weights/best.pt",
}

# Also check if Phase 1 best still exists
phase1_candidates = [
    "/home/rndpig/deer-deterrent/runs/train/deer_v2_20260206_2011_phase12/weights/best.pt",
    "/home/rndpig/deer-deterrent/runs/train/deer_v2_20260206_2011_phase1/weights/best.pt",
]
for p in phase1_candidates:
    if os.path.exists(p):
        models["YOLO26s Phase 1 only"] = p
        break

print("=" * 75)
print("MODEL COMPARISON")
print("=" * 75)

for name, path in models.items():
    print(f"\n--- {name} ---")
    print(f"  Path: {path}")
    size_mb = os.path.getsize(path) / (1024 * 1024)
    print(f"  File size: {size_mb:.2f} MB")
    
    try:
        m = YOLO(path)
        # Get model type from the YAML or task
        model_type = getattr(m, 'model_name', 'unknown')
        task = getattr(m, 'task', 'unknown')
        
        # Get architecture info
        info = m.info(verbose=False)
        layers, params, gflops = info[0], info[1], info[2]
        print(f"  Architecture: {m.ckpt.get('model').yaml.get('yaml_file', 'unknown') if hasattr(m, 'ckpt') and m.ckpt else 'unknown'}")
        print(f"  Layers (fused): {layers}")
        print(f"  Parameters: {params:,}")
        print(f"  GFLOPs: {gflops}")
        
        # Try to get training info from checkpoint
        if hasattr(m, 'ckpt') and m.ckpt:
            ckpt = m.ckpt
            if 'train_args' in ckpt:
                args = ckpt['train_args']
                print(f"  Trained with imgsz: {args.get('imgsz', 'N/A')}")
                print(f"  Trained with batch: {args.get('batch', 'N/A')}")
                print(f"  Epochs trained: {ckpt.get('epoch', 'N/A')}")
                print(f"  Best epoch fitness: {ckpt.get('best_fitness', 'N/A')}")
            # Check model YAML
            model_yaml = ckpt.get('model', None)
            if model_yaml and hasattr(model_yaml, 'yaml'):
                yaml_data = model_yaml.yaml
                print(f"  YAML scales: {yaml_data.get('scale', 'N/A')}")
                arch_file = yaml_data.get('yaml_file', 'N/A')
                print(f"  Base architecture file: {arch_file}")
    except Exception as e:
        print(f"  Error loading: {e}")

# Load and print summary JSON if available
summary_path = "/home/rndpig/deer-deterrent/runs/train/deer_v2_20260206_2011_summary.json"
if os.path.exists(summary_path):
    print(f"\n--- Training Summary JSON ---")
    with open(summary_path) as f:
        summary = json.load(f)
    print(json.dumps(summary, indent=2))
else:
    print(f"\nNo summary JSON found at {summary_path}")

# Check MD5 hashes to verify models are different
import hashlib
print(f"\n--- Model Identity Verification (MD5) ---")
for name, path in models.items():
    md5 = hashlib.md5(open(path, 'rb').read()).hexdigest()
    print(f"  {name}: {md5}")
