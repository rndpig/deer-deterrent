#!/usr/bin/env python3
"""
Update models/registry.json after a training run.

Reads the training summary JSON, extracts metrics and metadata,
appends a new model entry, retires the previous production model,
and updates the VERSION file.

Usage:
    python3 scripts/update_registry.py \
        --summary runs/train/deer_v2_20260411_0922_summary.json \
        --model dell-deployment/models/production/best.pt \
        --dataset-dir data/training_datasets/v3.0_20260411

Called automatically by train_pipeline.sh after deployment.
"""

import argparse
import json
import hashlib
import re
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = PROJECT_ROOT / "models" / "registry.json"
VERSION_PATH = PROJECT_ROOT / "dell-deployment" / "models" / "production" / "VERSION"


def compute_md5(filepath: Path) -> str:
    """Compute MD5 hash of a file."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def count_dataset_images(dataset_dir: Path) -> dict:
    """Count images per split in a YOLO dataset."""
    stats = {}
    images_dir = dataset_dir / "images"
    if images_dir.exists():
        for split in ["train", "val", "test"]:
            split_dir = images_dir / split
            if split_dir.exists():
                stats[f"{split}_images"] = len(list(split_dir.glob("*.jpg")) + list(split_dir.glob("*.png")))
        stats["total_images"] = sum(v for k, v in stats.items() if k.endswith("_images"))
    return stats


def determine_next_version(registry: dict) -> str:
    """Determine the next model version from existing entries."""
    max_major = 0
    for m in registry.get("models", []):
        match = re.search(r'(\d+)\.0\.0', m.get("version", ""))
        if match:
            max_major = max(max_major, int(match.group(1)))
    return f"{max_major + 1}.0.0"


def main():
    parser = argparse.ArgumentParser(description="Update model registry after training")
    parser.add_argument("--summary", required=True, help="Path to training summary JSON")
    parser.add_argument("--model", required=True, help="Path to deployed best.pt")
    parser.add_argument("--dataset-dir", required=True, help="Path to dataset directory")
    parser.add_argument("--notes", default="", help="Optional notes for the registry entry")
    args = parser.parse_args()

    summary_path = Path(args.summary)
    model_path = Path(args.model)
    dataset_dir = Path(args.dataset_dir)

    if not summary_path.exists():
        print(f"ERROR: Summary not found: {summary_path}")
        sys.exit(1)
    if not model_path.exists():
        print(f"ERROR: Model not found: {model_path}")
        sys.exit(1)

    # Load training summary
    with open(summary_path) as f:
        summary = json.load(f)

    # Load existing registry
    if REGISTRY_PATH.exists():
        with open(REGISTRY_PATH) as f:
            registry = json.load(f)
    else:
        print(f"ERROR: Registry not found: {REGISTRY_PATH}")
        sys.exit(1)

    # Determine version
    next_version = determine_next_version(registry)
    major = next_version.split(".")[0]
    arch = summary.get("architecture", "YOLO26s")
    model_id = f"yolo26s_v{major}.0"
    version_label = f"{arch} v{major}.0"
    ds_version = summary.get("dataset_version", "unknown")

    # Compute file hash
    file_hash = compute_md5(model_path)

    # Dataset stats
    ds_stats = count_dataset_images(dataset_dir) if dataset_dir.exists() else {}

    # Build test metrics
    test_metrics = summary.get("test_metrics", {})

    # Retire current production model
    for m in registry["models"]:
        if m.get("deployment", {}).get("status") == "deployed":
            m["deployment"]["status"] = "retired"
            m["deployment"]["retired_at"] = datetime.now().strftime("%Y-%m-%d")
            m["deployment"]["notes"] = m["deployment"].get("notes", "") + f" Replaced by {version_label}."
            # Add retirement to deployment history
            registry.setdefault("deployment_history", []).append({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "model_id": m["model_id"],
                "action": "retired",
                "environment": "production",
                "notes": f"Replaced by {version_label}"
            })

    # Build new model entry
    new_entry = {
        "model_id": model_id,
        "name": f"{version_label} - Production",
        "version": next_version,
        "framework": "ultralytics",
        "architecture": arch.lower().replace(" ", ""),
        "model_path": "models/production/best.pt",
        "dataset_version": ds_version,
        "dataset_notes": f"{ds_stats.get('total_images', '?')} images. CLAHE preprocessed.",
        "training_date": datetime.now().strftime("%Y-%m-%d"),
        "training_config": {
            "phase1_epochs": summary.get("phase1_epochs", 20),
            "phase2_epochs": summary.get("phase2_epochs"),
            "batch_size": summary.get("batch_size", 8),
            "image_size": 640,
            "augmentation": "mosaic + mixup + copy_paste + CLAHE preprocessing",
            "optimizer": "AdamW",
            "freeze_layers": "10 (phase1 only)"
        },
        "metrics": {
            "test": {
                "mAP50": test_metrics.get("map50"),
                "mAP50_95": test_metrics.get("map50_95"),
                "precision": test_metrics.get("precision"),
                "recall": test_metrics.get("recall")
            },
            "confidence_threshold": 0.55
        },
        "performance": {
            "inference_format": "pytorch",
            "device": "cpu (i7-4790)",
            "model_size_mb": summary.get("model_size_mb")
        },
        "preprocessing": {
            "clahe_enabled": True,
            "clahe_clip_limit": 2.0,
            "clahe_tile_grid_size": [8, 8]
        },
        "deployment": {
            "status": "deployed",
            "environment": "production",
            "service": "ml-detector",
            "deployed_at": datetime.now().strftime("%Y-%m-%d"),
            "notes": args.notes or f"Auto-registered by train_pipeline.sh"
        },
        "file_hash_md5": file_hash,
        "git_commit": None,
        "notes": f"Trained on Dell server (i7-4790 CPU). Dataset v{ds_version}."
    }

    registry["models"].append(new_entry)
    registry["updated_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Add deployment history entry
    registry.setdefault("deployment_history", []).append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "model_id": model_id,
        "action": "deployed",
        "environment": "production",
        "notes": f"Dataset v{ds_version}. Test mAP50={test_metrics.get('map50', 'N/A')}"
    })

    # Write updated registry
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)

    # Update VERSION file
    VERSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERSION_PATH.write_text(version_label)

    print(f"  Registry updated: {model_id} ({version_label})")
    print(f"  VERSION file:     {VERSION_PATH} → {version_label}")
    print(f"  File hash:        {file_hash}")
    if test_metrics:
        print(f"  Test mAP50:       {test_metrics.get('map50', 'N/A')}")
    print(f"  Previous model retired.")


if __name__ == "__main__":
    main()
