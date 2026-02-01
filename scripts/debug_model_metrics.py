#!/usr/bin/env python3
"""
Debug YOLOv8n model and dataset to understand why metrics are low
"""

import sys
sys.path.insert(0, '/home/rndpig/.local/lib/python3.12/site-packages')

from ultralytics import YOLO
import yaml
from pathlib import Path

print("=" * 80)
print("DEBUGGING MODEL & DATASET")
print("=" * 80)

# Load model
model_path = "models/production/best.pt"
model = YOLO(model_path)

print("\n### MODEL INFO ###")
print(f"Model path: {model_path}")
print(f"Model names: {model.names}")
print(f"Number of classes: {len(model.names)}")

# Load dataset config
data_yaml = "data/training_datasets/v1.0_2026-01-baseline/data.yaml"
with open(data_yaml, 'r') as f:
    data_config = yaml.safe_load(f)

print("\n### DATASET INFO ###")
print(f"Dataset path: {data_yaml}")
print(f"Dataset names: {data_config.get('names')}")
print(f"Number of classes: {data_config.get('nc')}")

# Check if class names match
model_classes = list(model.names.values())
dataset_classes = list(data_config.get('names', {}).values())

print("\n### CLASS COMPARISON ###")
print(f"Model classes: {model_classes}")
print(f"Dataset classes: {dataset_classes}")
print(f"Match: {model_classes == dataset_classes}")

# Run validation with verbose output
print("\n### RUNNING VALIDATION (VERBOSE) ###")
metrics = model.val(
    data=data_yaml,
    imgsz=640,
    device='cpu',
    batch=1,
    conf=0.001,
    iou=0.6,
    verbose=True
)

print("\n### DETAILED METRICS ###")
print(f"mAP50: {float(metrics.box.map50):.4f}")
print(f"mAP50-95: {float(metrics.box.map):.4f}")
print(f"Precision: {float(metrics.box.p)}")
print(f"Recall: {float(metrics.box.r)}")
print(f"Total predictions: {metrics.box.tp}")
print(f"False positives: {metrics.box.fp}")
print(f"Ground truth: {metrics.box}")
