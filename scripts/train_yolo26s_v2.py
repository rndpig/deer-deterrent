#!/usr/bin/env python3
"""
Train YOLO26s on v2.0 dataset — designed for Google Colab T4 GPU.

This script can be run either:
  1. In Google Colab (recommended) — copy cells into a Colab notebook
  2. On any machine with a GPU
  3. On CPU (very slow — hours instead of minutes)

Prerequisites:
  - Dataset exported by scripts/export_dataset_v2.py
  - Dataset uploaded to Google Drive or Colab session
  - pip install ultralytics>=8.4.0

Usage:
  python3 scripts/train_yolo26s_v2.py --data /path/to/dataset_v2.0/data.yaml
"""

import argparse
import os
import sys
import json
import shutil
from datetime import datetime
from pathlib import Path


def check_environment():
    """Check that the training environment is properly set up."""
    print("=" * 70)
    print("Environment Check")
    print("=" * 70)
    
    # Check ultralytics version
    try:
        import ultralytics
        version = ultralytics.__version__
        print(f"  ultralytics: {version}")
        
        major, minor, patch = version.split('.')[:3]
        if int(major) < 8 or (int(major) == 8 and int(minor) < 4):
            print(f"  ⚠️  WARNING: ultralytics {version} may not support YOLO26.")
            print(f"     YOLO26 requires ultralytics >= 8.4.0")
            print(f"     Run: pip install --upgrade ultralytics")
            return False
    except ImportError:
        print("  ❌ ultralytics not installed. Run: pip install ultralytics>=8.4.0")
        return False
    
    # Check GPU
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_mem / 1e9
            print(f"  GPU: {gpu_name} ({gpu_mem:.1f} GB)")
            device = "cuda"
        else:
            print(f"  GPU: None (CPU training will be very slow)")
            device = "cpu"
    except ImportError:
        print("  GPU: Unknown (torch not found)")
        device = "cpu"
    
    # Check OpenCV (for CLAHE during inference later)
    try:
        import cv2
        print(f"  OpenCV: {cv2.__version__}")
    except ImportError:
        print(f"  OpenCV: not installed (optional)")
    
    print(f"  Device: {device}")
    print()
    return True


def train_yolo26s(data_yaml: str, output_dir: str = "runs/train", 
                  epochs: int = 150, batch_size: int = 16, 
                  device: str = "auto", resume: bool = False):
    """
    Train YOLO26s model on deer detection dataset.
    
    Two-phase training:
      Phase 1: Backbone frozen (20 epochs) — adapt detection head to deer
      Phase 2: Full fine-tune (remaining epochs) — optimize entire network
    """
    from ultralytics import YOLO
    import torch
    
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    
    run_name = f"yolo26s_deer_v2_{datetime.now().strftime('%Y%m%d_%H%M')}"
    
    print("=" * 70)
    print(f"YOLO26s Training — Deer Detector v2.0")
    print("=" * 70)
    print(f"  Dataset:    {data_yaml}")
    print(f"  Output:     {output_dir}/{run_name}")
    print(f"  Epochs:     {epochs}")
    print(f"  Batch size: {batch_size}")
    print(f"  Device:     {device}")
    print(f"  Resume:     {resume}")
    print()
    
    # Try to load YOLO26s; fallback to YOLOv8s if not available
    model_name = "yolo26s.pt"
    fallback_name = "yolov8s.pt"
    
    try:
        print(f"Loading {model_name}...")
        model = YOLO(model_name)
        architecture = "YOLO26s"
        print(f"  ✅ Loaded {model_name} (real YOLO26s)")
    except Exception as e:
        print(f"  ⚠️  Could not load {model_name}: {e}")
        print(f"  Falling back to {fallback_name}...")
        try:
            model = YOLO(fallback_name)
            architecture = "YOLOv8s"
            print(f"  ✅ Loaded {fallback_name} (YOLOv8s fallback)")
        except Exception as e2:
            print(f"  ❌ Could not load fallback either: {e2}")
            sys.exit(1)
    
    # =========================================
    # Phase 1: Frozen backbone (20 epochs)
    # =========================================
    phase1_epochs = min(20, epochs)
    
    print(f"\n{'='*70}")
    print(f"Phase 1: Frozen backbone training ({phase1_epochs} epochs)")
    print(f"{'='*70}")
    print("  Freezing backbone layers to adapt detection head first...")
    
    results1 = model.train(
        data=data_yaml,
        epochs=phase1_epochs,
        imgsz=640,
        batch=batch_size,
        device=device,
        project=output_dir,
        name=f"{run_name}_phase1",
        
        # Freeze backbone (first 10 layers)
        freeze=10,
        
        # Optimizer
        optimizer="AdamW",
        lr0=0.01,
        lrf=0.01,           # Cosine decay to 1% of initial LR
        weight_decay=0.0005,
        warmup_epochs=3,
        
        # Augmentation
        hsv_h=0.02,
        hsv_s=0.7,
        hsv_v=0.5,
        translate=0.15,
        scale=0.5,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.1,
        
        # Other
        patience=0,          # No early stopping in phase 1
        verbose=True,
        plots=True,
        save=True,
    )
    
    # Get the best model from phase 1
    phase1_best = Path(output_dir) / f"{run_name}_phase1" / "weights" / "best.pt"
    if not phase1_best.exists():
        phase1_best = Path(output_dir) / f"{run_name}_phase1" / "weights" / "last.pt"
    
    # =========================================
    # Phase 2: Full fine-tune (remaining epochs)
    # =========================================
    phase2_epochs = epochs - phase1_epochs
    
    if phase2_epochs > 0:
        print(f"\n{'='*70}")
        print(f"Phase 2: Full fine-tune ({phase2_epochs} epochs)")
        print(f"{'='*70}")
        print(f"  Loading best from Phase 1: {phase1_best}")
        
        model2 = YOLO(str(phase1_best))
        
        results2 = model2.train(
            data=data_yaml,
            epochs=phase2_epochs,
            imgsz=640,
            batch=batch_size,
            device=device,
            project=output_dir,
            name=f"{run_name}_phase2",
            
            # No freeze — full fine-tune
            freeze=0,
            
            # Lower learning rate for fine-tuning
            optimizer="AdamW",
            lr0=0.001,          # 10x lower than phase 1
            lrf=0.01,
            weight_decay=0.0005,
            warmup_epochs=0,
            
            # Same augmentation
            hsv_h=0.02,
            hsv_s=0.7,
            hsv_v=0.5,
            translate=0.15,
            scale=0.5,
            fliplr=0.5,
            mosaic=1.0,
            mixup=0.15,
            copy_paste=0.1,
            
            # Early stopping
            patience=30,
            verbose=True,
            plots=True,
            save=True,
        )
        
        final_best = Path(output_dir) / f"{run_name}_phase2" / "weights" / "best.pt"
    else:
        final_best = phase1_best
    
    # =========================================
    # Evaluate on test set
    # =========================================
    print(f"\n{'='*70}")
    print("Evaluation on test set")
    print(f"{'='*70}")
    
    if final_best.exists():
        eval_model = YOLO(str(final_best))
        metrics = eval_model.val(
            data=data_yaml,
            split="test",
            imgsz=640,
            batch=batch_size,
            device=device,
            verbose=True,
        )
        
        print(f"\n  Test Results:")
        print(f"    mAP50:    {metrics.box.map50:.4f}")
        print(f"    mAP50-95: {metrics.box.map:.4f}")
        print(f"    Precision: {metrics.box.mp:.4f}")
        print(f"    Recall:    {metrics.box.mr:.4f}")
    
    # =========================================
    # Export to ONNX and OpenVINO for deployment
    # =========================================
    print(f"\n{'='*70}")
    print("Exporting model for deployment")
    print(f"{'='*70}")
    
    if final_best.exists():
        deploy_model = YOLO(str(final_best))
        
        # Export ONNX
        try:
            onnx_path = deploy_model.export(format="onnx", imgsz=640, simplify=True)
            print(f"  ✅ ONNX: {onnx_path}")
        except Exception as e:
            print(f"  ⚠️  ONNX export failed: {e}")
        
        # Export OpenVINO FP16 (for Dell i7-4790 deployment)
        try:
            ov_path = deploy_model.export(format="openvino", imgsz=640, half=True)
            print(f"  ✅ OpenVINO FP16: {ov_path}")
        except Exception as e:
            print(f"  ⚠️  OpenVINO export failed: {e}")
            print(f"       This is expected on Colab — export on Dell server instead")
    
    # =========================================
    # Save training summary
    # =========================================
    summary = {
        'architecture': architecture,
        'dataset_version': '2.0',
        'data_yaml': str(data_yaml),
        'device': device,
        'epochs': epochs,
        'batch_size': batch_size,
        'phase1_epochs': phase1_epochs,
        'phase2_epochs': phase2_epochs,
        'final_model': str(final_best),
        'timestamp': datetime.now().isoformat(),
    }
    
    if final_best.exists():
        summary['model_size_mb'] = final_best.stat().st_size / 1e6
        summary['test_map50'] = float(metrics.box.map50) if 'metrics' in dir() else None
        summary['test_map50_95'] = float(metrics.box.map) if 'metrics' in dir() else None
    
    summary_path = Path(output_dir) / f"{run_name}_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*70}")
    print("TRAINING COMPLETE!")
    print(f"{'='*70}")
    print(f"  Best model: {final_best}")
    print(f"  Summary:    {summary_path}")
    print(f"\n  Next steps:")
    print(f"    1. Download best.pt from Colab")
    print(f"    2. Copy to Dell server: models/production/best.pt")
    print(f"    3. Export to OpenVINO on server if not done above")
    print(f"    4. Restart ml-detector container")
    print(f"{'='*70}")
    
    return str(final_best)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train YOLO26s deer detector v2.0")
    parser.add_argument("--data", required=True, help="Path to data.yaml")
    parser.add_argument("--output", default="runs/train", help="Output directory")
    parser.add_argument("--epochs", type=int, default=150, help="Total training epochs")
    parser.add_argument("--batch", type=int, default=16, help="Batch size")
    parser.add_argument("--device", default="auto", help="Device (cuda/cpu/auto)")
    parser.add_argument("--resume", action="store_true", help="Resume training")
    
    args = parser.parse_args()
    
    if not check_environment():
        print("\nEnvironment check failed. Fix issues above and retry.")
        sys.exit(1)
    
    train_yolo26s(
        data_yaml=args.data,
        output_dir=args.output,
        epochs=args.epochs,
        batch_size=args.batch,
        device=args.device,
        resume=args.resume,
    )
