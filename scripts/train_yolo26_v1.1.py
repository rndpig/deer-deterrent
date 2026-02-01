"""
Train YOLO26n on v1.1 pseudo-labeled dataset.
"""
from ultralytics import YOLO
import os
from datetime import datetime

print("\n" + "="*70)
print("YOLO26n Training - v1.1 Pseudo-Labeled Dataset")
print("="*70)
print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Configuration
DATA_YAML = "data/training_datasets/v1.1_2026-01-pseudolabels/data.yaml"
MODEL = "yolo26n.pt"
EPOCHS = 100
IMGSZ = 640
BATCH = 8
DEVICE = "cpu"
PROJECT = "runs/train"
NAME = "yolo26n_v1.1"

print(f"\nConfiguration:")
print(f"  Dataset: {DATA_YAML}")
print(f"  Model: {MODEL}")
print(f"  Epochs: {EPOCHS}")
print(f"  Image size: {IMGSZ}")
print(f"  Batch size: {BATCH}")
print(f"  Device: {DEVICE}")
print(f"  Output: {PROJECT}/{NAME}")

# Load model
print(f"\nLoading model...")
model = YOLO(MODEL)

# Train
print(f"\n{'='*70}")
print("Starting training...")
print(f"{'='*70}\n")

results = model.train(
    data=DATA_YAML,
    epochs=EPOCHS,
    imgsz=IMGSZ,
    batch=BATCH,
    device=DEVICE,
    project=PROJECT,
    name=NAME,
    verbose=True
)

print(f"\n{'='*70}")
print("Training Complete!")
print(f"{'='*70}")
print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Results saved to: {PROJECT}/{NAME}")
print(f"\nNext: Benchmark model and compare with YOLOv8n baseline")
print(f"  YOLOv8n: 53.3ms inference, 1.16 det/img")
print(f"{'='*70}\n")
