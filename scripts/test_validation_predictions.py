#!/usr/bin/env python3
"""
Test the model on a few validation images to see actual predictions
"""

import sys
sys.path.insert(0, '/home/rndpig/.local/lib/python3.12/site-packages')

from ultralytics import YOLO
from pathlib import Path
import json

model_path = "models/production/best.pt"
val_images_dir = Path("data/training_datasets/v1.0_2026-01-baseline/images/val")

print("=" * 80)
print("TESTING MODEL ON VALIDATION IMAGES")
print("=" * 80)

model = YOLO(model_path)

# Get first 5 validation images
val_images = sorted(list(val_images_dir.glob("*.jpg")))[:5]

for img_path in val_images:
    print(f"\n### {img_path.name} ###")
    
    # Run prediction
    results = model.predict(
        source=str(img_path),
        conf=0.001,  # Very low threshold
        iou=0.6,
        verbose=False
    )[0]
    
    # Check ground truth
    label_path = Path("data/training_datasets/v1.0_2026-01-baseline/labels/val") / (img_path.stem + ".txt")
    gt_boxes = []
    if label_path.exists():
        with open(label_path) as f:
            gt_boxes = f.readlines()
    
    print(f"Ground truth boxes: {len(gt_boxes)}")
    print(f"Predicted boxes: {len(results.boxes)}")
    
    if len(results.boxes) > 0:
        print("Predictions:")
        for box in results.boxes:
            conf = float(box.conf[0])
            cls = int(box.cls[0])
            print(f"  Class: {model.names[cls]}, Confidence: {conf:.4f}")
    else:
        print("  No detections!")
    
    # Show ground truth
    if gt_boxes:
        print("Ground truth (first 3):")
        for gt in gt_boxes[:3]:
            parts = gt.strip().split()
            print(f"  Class: {parts[0]}, Center: ({parts[1]}, {parts[2]}), Size: ({parts[3]}, {parts[4]})")
