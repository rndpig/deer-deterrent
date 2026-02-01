#!/usr/bin/env python3
"""
Test different confidence thresholds to understand metrics
"""

import sys
sys.path.insert(0, '/home/rndpig/.local/lib/python3.12/site-packages')

from ultralytics import YOLO

model = YOLO("models/production/best.pt")
data_yaml = "data/training_datasets/v1.0_2026-01-baseline/data.yaml"

print("=" * 80)
print("TESTING DIFFERENT CONFIDENCE THRESHOLDS")
print("=" * 80)

for conf_thresh in [0.001, 0.1, 0.25, 0.5, 0.75]:
    print(f"\n### Confidence Threshold: {conf_thresh} ###")
    
    metrics = model.val(
        data=data_yaml,
        imgsz=640,
        device='cpu',
        batch=1,
        conf=conf_thresh,
        iou=0.45,  # Standard COCO IoU
        verbose=False
    )
    
    print(f"mAP50: {float(metrics.box.map50):.4f}")
    print(f"mAP50-95: {float(metrics.box.map):.4f}")
    print(f"Precision: {float(metrics.box.p):.4f}")
    print(f"Recall: {float(metrics.box.r):.4f}")
