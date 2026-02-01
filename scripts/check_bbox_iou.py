#!/usr/bin/env python3
"""
Compare predicted vs ground truth bboxes to understand IoU issue
"""

import sys
sys.path.insert(0, '/home/rndpig/.local/lib/python3.12/site-packages')

from ultralytics import YOLO
from pathlib import Path

model = YOLO("models/production/best.pt")

# Test on first validation image
img_path = "data/training_datasets/v1.0_2026-01-baseline/images/val/frame_000750_69889f5a230b51e5.jpg"
label_path = "data/training_datasets/v1.0_2026-01-baseline/labels/val/frame_000750_69889f5a230b51e5.txt"

print("=" * 80)
print("BBOX COORDINATE COMPARISON")
print("=" * 80)
print(f"\nImage: {Path(img_path).name}\n")

# Get predictions
results = model.predict(source=img_path, conf=0.001, verbose=False)[0]

# Get ground truth
with open(label_path) as f:
    gt_lines = f.readlines()

print("### GROUND TRUTH (YOLO format: class x_center y_center width height) ###")
for i, line in enumerate(gt_lines):
    parts = line.strip().split()
    print(f"GT {i+1}: class={parts[0]}, x_center={parts[1]}, y_center={parts[2]}, w={parts[3]}, h={parts[4]}")

print("\n### PREDICTIONS (normalized coordinates) ###")
if len(results.boxes) > 0:
    for i, box in enumerate(results.boxes):
        # Get normalized xywh
        xywh_norm = box.xywhn[0]  # normalized xywh format
        conf = float(box.conf[0])
        print(f"Pred {i+1}: conf={conf:.4f}, x_center={float(xywh_norm[0]):.6f}, y_center={float(xywh_norm[1]):.6f}, w={float(xywh_norm[2]):.6f}, h={float(xywh_norm[3]):.6f}")
else:
    print("No predictions!")

print("\n### IoU ANALYSIS ###")
print("Checking if predictions match ground truth...")

# Compare first 3 predictions with first 3 ground truth
for pred_idx in range(min(3, len(results.boxes))):
    pred_box = results.boxes[pred_idx]
    pred_xywh = pred_box.xywhn[0]
    
    for gt_idx in range(min(3, len(gt_lines))):
        gt_parts = gt_lines[gt_idx].strip().split()
        gt_x, gt_y, gt_w, gt_h = map(float, gt_parts[1:5])
        
        # Calculate IoU manually
        pred_x1 = float(pred_xywh[0]) - float(pred_xywh[2])/2
        pred_y1 = float(pred_xywh[1]) - float(pred_xywh[3])/2
        pred_x2 = float(pred_xywh[0]) + float(pred_xywh[2])/2
        pred_y2 = float(pred_xywh[1]) + float(pred_xywh[3])/2
        
        gt_x1 = gt_x - gt_w/2
        gt_y1 = gt_y - gt_h/2
        gt_x2 = gt_x + gt_w/2
        gt_y2 = gt_y + gt_h/2
        
        # Intersection
        inter_x1 = max(pred_x1, gt_x1)
        inter_y1 = max(pred_y1, gt_y1)
        inter_x2 = min(pred_x2, gt_x2)
        inter_y2 = min(pred_y2, gt_y2)
        
        inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
        
        pred_area = float(pred_xywh[2]) * float(pred_xywh[3])
        gt_area = gt_w * gt_h
        
        union_area = pred_area + gt_area - inter_area
        iou = inter_area / union_area if union_area > 0 else 0
        
        print(f"Pred {pred_idx+1} vs GT {gt_idx+1}: IoU = {iou:.4f}")
