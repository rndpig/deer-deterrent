"""
Test validation metrics with different IoU thresholds for matching.
Based on IoU analysis showing max IoU of 0.334 between predictions and GT.
"""
from ultralytics import YOLO
import os

# Load the baseline YOLOv8n model
model_path = "models/production/best.pt"
data_yaml = "data/training_datasets/v1.0_2026-01-baseline/data.yaml"

print("\n" + "="*60)
print("Testing YOLOv8n with Different IoU Thresholds")
print("="*60)
print(f"Model: {model_path}")
print(f"Dataset: {data_yaml}")
print(f"Confidence: 0.25 (production-like)")
print()

model = YOLO(model_path)

# Test different IoU thresholds for NMS/matching
iou_thresholds = [0.3, 0.35, 0.4, 0.45, 0.5]

for iou_thresh in iou_thresholds:
    print(f"\n{'='*60}")
    print(f"IoU Threshold: {iou_thresh}")
    print(f"{'='*60}")
    
    metrics = model.val(
        data=data_yaml,
        conf=0.25,  # production-like confidence
        iou=iou_thresh,
        verbose=False
    )
    
    results = metrics.results_dict
    print(f"  mAP50:     {results['metrics/mAP50(B)']:.4f}")
    print(f"  mAP50-95:  {results['metrics/mAP50-95(B)']:.4f}")
    print(f"  Precision: {results['metrics/precision(B)']:.4f}")
    print(f"  Recall:    {results['metrics/recall(B)']:.4f}")

print("\n" + "="*60)
print("Analysis:")
print("- IoU threshold controls when a prediction 'matches' ground truth")
print("- Lower IoU = more lenient matching = higher metrics")
print("- Our max observed IoU was 0.334, so thresholds > 0.334 will give 0.0")
print("="*60)
