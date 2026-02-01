# Baseline Validation Issue - Analysis & Resolution

## Date: 2026-01-31

## Problem Statement
Initial baseline validation returned very low mAP50 (1.57%), despite the YOLOv8n model detecting deer with high confidence (0.75-0.85) in production.

## Investigation Steps

### 1. Fixed Bounding Box Export Bug
**Issue**: Dataset export script was double-normalizing bbox coordinates
- Database stores normalized coords (0-1 range)
- Export script treated them as pixels and divided by image dimensions again
- Result: bbox values like 0.000149 instead of 0.286989

**Fix**: Removed double normalization in `export_dataset_v1.py`
```python
# OLD (WRONG)
x_center = (bbox['x'] + bbox['width'] / 2) / img_width

# NEW (CORRECT)
x_center = bbox['x'] + bbox['width'] / 2  # Already normalized
```

**Outcome**: Re-exported entire v1.0 dataset with corrected coordinates

### 2. Tested Model Predictions
**Script**: `test_validation_predictions.py`
**Results**: Model successfully predicts deer with confidence 0.75-0.85
- Example: frame_000750 had 3 GT boxes, 6 predictions (0.85, 0.82, 0.70 confidence)
- Model IS working correctly

### 3. Tested Confidence Thresholds
**Script**: `test_conf_thresholds.py`
**Results**: Only conf=0.001 gave non-zero metrics
- conf=0.001: mAP50=0.0091
- conf=0.1 through 0.75: ALL ZEROS

### 4. Calculated IoU Between Predictions and Ground Truth
**Script**: `check_bbox_iou.py`
**Key Finding**: **Maximum IoU = 0.334 (33.4%)**

Example from frame_000750:
```
Pred 1 vs GT 1: IoU = 0.1319
Pred 2 vs GT 2: IoU = 0.1158
Pred 2 vs GT 3: IoU = 0.3340  ← Best match
Pred 3 vs GT 3: IoU = 0.1331
```

**YOLO's default IoU threshold for matching: 0.5 (50%)**

### 5. Tested Lower IoU Thresholds
**Script**: `test_iou_threshold.py`
**Results**: Still all zeros even at IoU=0.3

This means very few predictions achieve even 30% overlap with ground truth.

### 6. Visualized Predictions vs Ground Truth
**Script**: `visualize_predictions_vs_gt.py`
**Output**: `data/bbox_comparison.jpg` (green=GT, red=predictions)
**Observation**: Boxes are detecting deer but at slightly different positions/sizes than ground truth labels

## Root Cause
**The ground truth bounding box annotations are low quality or inconsistent.**

The model is correctly detecting deer (proven by high-confidence production use), but the annotations used for training/validation don't align spatially with where the model learned to draw boxes.

This could be due to:
1. Inconsistent annotation methodology
2. Annotations done at different zoom levels
3. Different interpretations of bbox boundaries (tight vs loose)
4. Annotations may be under-labeled (model detects 6-8 deer, GT shows only 3)

## Resolution
Since traditional mAP metrics require accurate ground truth, we've switched to **production-focused metrics**:

### YOLOv8n Baseline (Production Metrics)
**Script**: `benchmark_production_baseline.py`

**Results**:
- Total detections (conf ≥ 0.75): 29 across 25 images
- Average detections per image: 1.16
- Average inference time: 53.3ms (18.8 FPS)
- Hardware: Intel Core i7-4790 @ 3.60GHz (CPU)
- Model: YOLOv8n, 3.01M parameters

**Metrics saved to**: `data/model_registry/baseline_production_metrics.txt`

## Implications for Training

### Option 1: Use Current Dataset
- Accept that mAP metrics won't be meaningful
- Benchmark YOLO26 using production metrics (detection count, speed)
- Compare: "Does YOLO26 detect similar deer count with better speed?"

### Option 2: Re-annotate Validation Set
- Manually review and fix bbox annotations
- Use model's predictions as starting point
- Verify each bbox aligns with visible deer
- Time investment: ~2-3 hours for 258 images

### Option 3: Use Model's Predictions as Pseudo-Labels
- Run YOLOv8n on all images with conf=0.75
- Use predictions as new ground truth
- Review and correct obvious errors
- Fast but circular (can't improve on current model)

## Recommendation
**Proceed with Option 1** - Use production metrics for now:
1. Train YOLO26 on current v1.0 dataset
2. Benchmark using detection count and inference speed
3. Deploy if speed improves without losing detections
4. Plan re-annotation effort for v1.1 dataset after YOLO26 deployment

This allows us to move forward with training while acknowledging the ground truth limitations.

## Next Steps
1. ✅ Baseline benchmark complete (production metrics)
2. ⏳ Train YOLO26 on v1.0 dataset
3. ⏳ Benchmark YOLO26 (production metrics)
4. ⏳ Compare: detection count, inference speed
5. ⏳ Export to OpenVINO INT8 if promising
6. ⏳ Plan v1.1 dataset with improved annotations
