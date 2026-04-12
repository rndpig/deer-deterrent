#!/usr/bin/env python3
"""
Compare new model against current production model before deployment.

Runs validation on both models using the same test split and prints
a side-by-side comparison. Optionally aborts if new model regresses.

Usage:
    python3 scripts/compare_before_deploy.py \
        --new-model runs/train/deer_v2_phase2/weights/best.pt \
        --current-model dell-deployment/models/production/best.pt \
        --data data/training_datasets/v3.0_20260411/data.yaml

    # Abort if new model is worse:
    python3 scripts/compare_before_deploy.py \
        --new-model ... --current-model ... --data ... --strict

Called by train_pipeline.sh before deploying to production.
"""

import argparse
import sys
from pathlib import Path


def validate_model(model_path: str, data_yaml: str, device: str = "cpu", batch: int = 8) -> dict:
    """Run YOLO val() on test split, return metrics dict."""
    from ultralytics import YOLO

    model = YOLO(model_path)
    metrics = model.val(
        data=data_yaml,
        split="test",
        imgsz=640,
        batch=batch,
        device=device,
        verbose=False,
    )
    return {
        "mAP50": float(metrics.box.map50),
        "mAP50-95": float(metrics.box.map),
        "precision": float(metrics.box.mp),
        "recall": float(metrics.box.mr),
    }


def main():
    parser = argparse.ArgumentParser(description="Compare new model vs current production")
    parser.add_argument("--new-model", required=True, help="Path to new best.pt")
    parser.add_argument("--current-model", required=True, help="Path to current production best.pt")
    parser.add_argument("--data", required=True, help="Path to data.yaml")
    parser.add_argument("--device", default="cpu", help="Device")
    parser.add_argument("--batch", type=int, default=8, help="Batch size")
    parser.add_argument("--strict", action="store_true",
                        help="Exit with error code 1 if new model mAP50 < current")
    args = parser.parse_args()

    new_path = Path(args.new_model)
    current_path = Path(args.current_model)

    if not new_path.exists():
        print(f"ERROR: New model not found: {new_path}")
        sys.exit(1)

    if not current_path.exists():
        print("  No current production model found — skipping comparison.")
        print("  RESULT: PASS (first deployment)")
        sys.exit(0)

    print("  Evaluating current production model...")
    current_metrics = validate_model(str(current_path), args.data, args.device, args.batch)

    print("  Evaluating new model...")
    new_metrics = validate_model(str(new_path), args.data, args.device, args.batch)

    # Print comparison table
    print()
    print(f"  {'Metric':<14} {'Current':>10} {'New':>10} {'Delta':>10}")
    print(f"  {'-'*14} {'-'*10} {'-'*10} {'-'*10}")

    all_improved = True
    map50_improved = True

    for key in ["mAP50", "mAP50-95", "precision", "recall"]:
        cur = current_metrics[key]
        new = new_metrics[key]
        delta = new - cur
        sign = "+" if delta >= 0 else ""
        marker = "✅" if delta >= 0 else "⚠️"
        print(f"  {key:<14} {cur:>10.4f} {new:>10.4f} {sign}{delta:>9.4f} {marker}")
        if delta < 0:
            all_improved = False
        if key == "mAP50" and delta < 0:
            map50_improved = False

    print()

    if all_improved:
        print("  RESULT: PASS — New model improves all metrics")
    elif map50_improved:
        print("  RESULT: PASS — New model improves mAP50 (some other metrics regressed)")
    else:
        print("  RESULT: WARNING — New model mAP50 is WORSE than current production")
        if args.strict:
            print("  ABORTING deployment (--strict mode)")
            sys.exit(1)
        else:
            print("  Proceeding anyway (use --strict to abort on regression)")

    sys.exit(0)


if __name__ == "__main__":
    main()
