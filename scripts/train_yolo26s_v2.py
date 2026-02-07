#!/usr/bin/env python3
"""
Train YOLO26s deer detector v2.0 — Dell server CPU-local training.

Designed to run directly on the Dell i7-4790 server. No GPU needed.
Expected training time: ~30-50 hours depending on dataset size.

Run in tmux so it survives SSH disconnection:
    tmux new -s train
    python3 scripts/train_yolo26s_v2.py --data /path/to/data.yaml
    # Ctrl+B, D to detach. tmux attach -t train to reconnect.

Or use the pipeline script:
    bash scripts/train_pipeline.sh
"""

import argparse
import os
import sys
import json
import shutil
from datetime import datetime
from pathlib import Path


def check_environment():
    """Verify the training environment is ready."""
    print("=" * 70)
    print("Environment Check")
    print("=" * 70)
    
    ok = True
    
    try:
        import ultralytics
        version = ultralytics.__version__
        print(f"  ultralytics: {version}")
        parts = version.split('.')
        if int(parts[0]) < 8 or (int(parts[0]) == 8 and int(parts[1]) < 4):
            print(f"  WARNING: YOLO26 requires ultralytics >= 8.4.0")
            print(f"  Run: pip3 install --upgrade ultralytics")
    except ImportError:
        print("  ERROR: ultralytics not installed")
        print("  Run: pip3 install ultralytics>=8.4.0")
        ok = False
    
    try:
        import torch
        print(f"  torch: {torch.__version__}")
        print(f"  CUDA: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  GPU: {torch.cuda.get_device_name(0)}")
    except ImportError:
        print("  torch: not installed")
        ok = False
    
    try:
        import cv2
        print(f"  OpenCV: {cv2.__version__}")
    except ImportError:
        print(f"  OpenCV: not installed (needed for CLAHE)")
    
    import multiprocessing
    print(f"  CPU cores: {multiprocessing.cpu_count()}")
    
    return ok


def train(data_yaml: str, output_dir: str = "runs/train",
          epochs: int = 150, batch_size: int = 8, device: str = "cpu"):
    """
    Two-phase YOLO training optimized for CPU.
    
    Phase 1 (20 epochs): Frozen backbone — head adapts to deer features
    Phase 2 (remaining):  Full fine-tune — entire network optimized
    """
    from ultralytics import YOLO
    
    data_yaml = str(Path(data_yaml).resolve())
    run_timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    run_name = f"deer_v2_{run_timestamp}"
    
    print("\n" + "=" * 70)
    print(f"Training: {run_name}")
    print("=" * 70)
    print(f"  Data:       {data_yaml}")
    print(f"  Output:     {output_dir}/{run_name}_*")
    print(f"  Epochs:     {epochs} ({min(20, epochs)} frozen + {max(0, epochs-20)} full)")
    print(f"  Batch:      {batch_size}")
    print(f"  Device:     {device}")
    print(f"  Started:    {datetime.now().isoformat()}")
    print()
    
    # ---- Load model ----
    # Try YOLO26s first (real YOLO26), fallback to YOLOv8s
    arch = None
    model = None
    for model_name, arch_name in [("yolo26s.pt", "YOLO26s"), ("yolov8s.pt", "YOLOv8s")]:
        try:
            print(f"Trying {model_name}...")
            model = YOLO(model_name)
            arch = arch_name
            print(f"  Loaded {arch}")
            break
        except Exception as e:
            print(f"  {model_name} not available: {e}")
    
    if model is None:
        print("ERROR: No model could be loaded")
        sys.exit(1)

    # ---- Phase 1: Frozen backbone ----
    phase1_epochs = min(20, epochs)
    
    print(f"\n{'='*70}")
    print(f"PHASE 1: Frozen backbone ({phase1_epochs} epochs)")
    print(f"{'='*70}")
    
    results1 = model.train(
        data=data_yaml,
        epochs=phase1_epochs,
        imgsz=640,
        batch=batch_size,
        device=device,
        project=output_dir,
        name=f"{run_name}_phase1",
        
        freeze=10,                # Freeze backbone layers
        
        optimizer="AdamW",
        lr0=0.01,
        lrf=0.01,
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
        
        patience=0,              # No early stopping in phase 1
        workers=2,               # CPU: fewer workers to avoid overload
        verbose=True,
        plots=True,
        save=True,
    )
    
    # Find the actual phase1 output dir (YOLO may append a number if dir exists)
    phase1_candidates = sorted(
        Path(output_dir).glob(f"{run_name}_phase1*/weights/best.pt"),
        key=lambda p: p.stat().st_mtime, reverse=True
    )
    if phase1_candidates:
        phase1_best = phase1_candidates[0]
    else:
        # Fallback to last.pt
        last_candidates = sorted(
            Path(output_dir).glob(f"{run_name}_phase1*/weights/last.pt"),
            key=lambda p: p.stat().st_mtime, reverse=True
        )
        phase1_best = last_candidates[0] if last_candidates else Path(output_dir) / f"{run_name}_phase1" / "weights" / "best.pt"
    
    print(f"\nPhase 1 complete. Best: {phase1_best}")
    
    # ---- Phase 2: Full fine-tune ----
    phase2_epochs = epochs - phase1_epochs
    
    if phase2_epochs > 0:
        print(f"\n{'='*70}")
        print(f"PHASE 2: Full fine-tune ({phase2_epochs} epochs)")
        print(f"{'='*70}")
        
        model2 = YOLO(str(phase1_best))
        
        results2 = model2.train(
            data=data_yaml,
            epochs=phase2_epochs,
            imgsz=640,
            batch=batch_size,
            device=device,
            project=output_dir,
            name=f"{run_name}_phase2",
            
            freeze=0,                # Full network
            
            optimizer="AdamW",
            lr0=0.001,              # 10x lower for fine-tuning
            lrf=0.01,
            weight_decay=0.0005,
            warmup_epochs=0,
            
            hsv_h=0.02,
            hsv_s=0.7,
            hsv_v=0.5,
            translate=0.15,
            scale=0.5,
            fliplr=0.5,
            mosaic=1.0,
            mixup=0.15,
            copy_paste=0.1,
            
            patience=30,            # Early stopping
            workers=2,
            verbose=True,
            plots=True,
            save=True,
        )
        
        # Find the actual phase2 output dir (YOLO may append a number)
        phase2_candidates = sorted(
            Path(output_dir).glob(f"{run_name}_phase2*/weights/best.pt"),
            key=lambda p: p.stat().st_mtime, reverse=True
        )
        if phase2_candidates:
            final_best = phase2_candidates[0]
        else:
            last_candidates = sorted(
                Path(output_dir).glob(f"{run_name}_phase2*/weights/last.pt"),
                key=lambda p: p.stat().st_mtime, reverse=True
            )
            final_best = last_candidates[0] if last_candidates else Path(output_dir) / f"{run_name}_phase2" / "weights" / "best.pt"
    else:
        final_best = phase1_best
    
    # ---- Evaluate on test split ----
    print(f"\n{'='*70}")
    print("Evaluation on test set")
    print(f"{'='*70}")
    
    test_metrics = {}
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
        
        test_metrics = {
            'map50': float(metrics.box.map50),
            'map50_95': float(metrics.box.map),
            'precision': float(metrics.box.mp),
            'recall': float(metrics.box.mr),
        }
        
        print(f"\n  Test Results:")
        print(f"    mAP50:     {test_metrics['map50']:.4f}")
        print(f"    mAP50-95:  {test_metrics['map50_95']:.4f}")
        print(f"    Precision: {test_metrics['precision']:.4f}")
        print(f"    Recall:    {test_metrics['recall']:.4f}")
    
    # ---- Save summary ----
    summary = {
        'architecture': arch,
        'dataset_version': '2.0',
        'data_yaml': data_yaml,
        'device': device,
        'epochs_total': epochs,
        'phase1_epochs': phase1_epochs,
        'phase2_epochs': phase2_epochs,
        'batch_size': batch_size,
        'final_model': str(final_best),
        'model_size_mb': round(final_best.stat().st_size / 1e6, 2) if final_best.exists() else None,
        'test_metrics': test_metrics,
        'started': run_timestamp,
        'completed': datetime.now().isoformat(),
    }
    
    summary_path = Path(output_dir) / f"{run_name}_summary.json"
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*70}")
    print("TRAINING COMPLETE")
    print(f"{'='*70}")
    print(f"  Model:   {final_best}")
    print(f"  Summary: {summary_path}")
    print(f"  Ended:   {datetime.now().isoformat()}")
    print(f"{'='*70}")
    
    return str(final_best), summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train YOLO26s deer detector (CPU)")
    parser.add_argument("--data", required=True, help="Path to data.yaml")
    parser.add_argument("--output", default="runs/train", help="Output directory")
    parser.add_argument("--epochs", type=int, default=150, help="Total epochs")
    parser.add_argument("--batch", type=int, default=8, help="Batch size (8 for CPU)")
    parser.add_argument("--device", default="cpu", help="Device (cpu or cuda)")
    
    args = parser.parse_args()
    
    if not check_environment():
        sys.exit(1)
    
    train(
        data_yaml=args.data,
        output_dir=args.output,
        epochs=args.epochs,
        batch_size=args.batch,
        device=args.device,
    )
