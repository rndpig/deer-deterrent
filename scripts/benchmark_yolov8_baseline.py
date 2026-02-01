#!/usr/bin/env python3
"""
Benchmark YOLOv8n baseline model on v1.0 dataset
Saves metrics to registry.json
"""

import sys
sys.path.insert(0, '/home/rndpig/.local/lib/python3.12/site-packages')

from ultralytics import YOLO
import json
from datetime import datetime
from pathlib import Path

def benchmark_model():
    """Run validation and save metrics"""
    
    print("=" * 80)
    print("BENCHMARKING YOLOv8n BASELINE MODEL")
    print("=" * 80)
    
    # Load model
    model_path = "models/production/best.pt"
    data_yaml = "data/training_datasets/v1.0_2026-01-baseline/data.yaml"
    
    print(f"\nModel: {model_path}")
    print(f"Dataset: {data_yaml}")
    print(f"Device: CPU (i7-4790)")
    print("\nRunning validation...")
    
    try:
        model = YOLO(model_path)
        
        # Run validation
        metrics = model.val(
            data=data_yaml,
            imgsz=640,
            device='cpu',
            batch=1,
            conf=0.25,  # Match production-like threshold (lowered from 0.75 for validation)
            iou=0.6
        )
        
        # Extract metrics
        results = {
            "mAP50": float(metrics.box.map50),
            "mAP50_95": float(metrics.box.map),
            "precision": float(metrics.box.p),
            "recall": float(metrics.box.r),
            "fitness": float(metrics.fitness),
            "confidence_threshold": 0.25,
            "validation_date": datetime.now().isoformat()
        }
        
        print("\n" + "=" * 80)
        print("RESULTS")
        print("=" * 80)
        print(f"mAP50:      {results['mAP50']:.4f}")
        print(f"mAP50-95:   {results['mAP50_95']:.4f}")
        print(f"Precision:  {results['precision']:.4f}")
        print(f"Recall:     {results['recall']:.4f}")
        print(f"Fitness:    {results['fitness']:.4f}")
        
        # Update registry
        registry_path = Path("models/registry.json")
        with open(registry_path, 'r') as f:
            registry = json.load(f)
        
        # Update baseline model metrics
        for model_entry in registry['models']:
            if model_entry['model_id'] == 'yolov8n_baseline':
                model_entry['metrics'] = results
                model_entry['validation_dataset'] = "v1.0_2026-01-baseline"
                break
        
        # Save updated registry
        with open(registry_path, 'w') as f:
            json.dump(registry, f, indent=2)
        
        print(f"\n✅ Registry updated: {registry_path}")
        
        # Save detailed results
        results_path = Path("models/yolov8n_baseline_validation_results.json")
        with open(results_path, 'w') as f:
            json.dump({
                "model": model_path,
                "dataset": data_yaml,
                "device": "cpu",
                "metrics": results,
                "validation_date": datetime.now().isoformat()
            }, f, indent=2)
        
        print(f"✅ Detailed results saved: {results_path}")
        
        return results
        
    except Exception as e:
        print(f"\n❌ Error during validation: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    benchmark_model()
