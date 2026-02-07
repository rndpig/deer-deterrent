#!/usr/bin/env python3
"""Phase 2 runner — continue from Phase 1 best weights."""
from ultralytics import YOLO
from pathlib import Path
import json
from datetime import datetime

phase1_best = '/home/rndpig/deer-deterrent/runs/train/deer_v2_20260206_2011_phase12/weights/best.pt'
data_yaml = '/home/rndpig/deer-deterrent/data/training_datasets/v2.0_20260206_200528/data.yaml'
output_dir = '/home/rndpig/deer-deterrent/runs/train'
run_name = 'deer_v2_20260206_2011'

SEP = '=' * 70
print(SEP)
print('PHASE 2: Full fine-tune (130 epochs)')
print(SEP)
print('Loading Phase 1 best: ' + phase1_best)

model2 = YOLO(phase1_best)

results2 = model2.train(
    data=data_yaml,
    epochs=130,
    imgsz=640,
    batch=8,
    device='cpu',
    project=output_dir,
    name=run_name + '_phase2',
    freeze=0,
    optimizer='AdamW',
    lr0=0.001,
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
    patience=30,
    workers=2,
    verbose=True,
    plots=True,
    save=True,
)

# Find best weights
phase2_dirs = sorted(
    Path(output_dir).glob(run_name + '_phase2*/weights/best.pt'),
    key=lambda p: p.stat().st_mtime, reverse=True
)
final_best = phase2_dirs[0] if phase2_dirs else Path(output_dir) / (run_name + '_phase2') / 'weights' / 'best.pt'

print('\nPhase 2 complete. Best: ' + str(final_best))

# Test evaluation
print(SEP)
print('Evaluation on test set')
print(SEP)
eval_model = YOLO(str(final_best))
metrics = eval_model.val(data=data_yaml, split='test', imgsz=640, batch=8, device='cpu', verbose=True)

test_metrics = {
    'map50': float(metrics.box.map50),
    'map50_95': float(metrics.box.map),
    'precision': float(metrics.box.mp),
    'recall': float(metrics.box.mr),
}

summary = {
    'architecture': 'YOLO26s',
    'dataset_version': '2.0',
    'phase1_best_map50': 0.676,
    'phase1_best_map50_95': 0.317,
    'test_metrics': test_metrics,
    'final_model': str(final_best),
    'model_size_mb': round(final_best.stat().st_size / 1e6, 2),
    'completed': datetime.now().isoformat(),
}

summary_path = Path(output_dir) / (run_name + '_summary.json')
with open(summary_path, 'w') as f:
    json.dump(summary, f, indent=2)

print('\n' + SEP)
print('TRAINING COMPLETE')
print(SEP)
print('  Model:      ' + str(final_best))
print('  Size:       ' + str(summary['model_size_mb']) + ' MB')
print('  Test mAP50:     %.4f' % test_metrics['map50'])
print('  Test mAP50-95:  %.4f' % test_metrics['map50_95'])
print('  Test Precision: %.4f' % test_metrics['precision'])
print('  Test Recall:    %.4f' % test_metrics['recall'])
print('  Summary:    ' + str(summary_path))
print(SEP)
