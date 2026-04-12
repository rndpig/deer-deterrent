# Training Pipeline Improvements

**Created**: 2026-04-11  
**Updated**: 2026-04-11  
**Status**: All improvements implemented and integrated into pipeline v3.0

## Overview

These improvements were identified during the v4.0 training cycle and have all been implemented.

---

## ✅ Implemented: VERSION File for Model Versioning

**Problem**: Model version was hardcoded in multiple files (ml-detector, coordinator, backend). Each deployment required updating version strings in 4+ places.

**Solution Implemented** (2026-04-11):

1. **VERSION file**: `dell-deployment/models/production/VERSION` contains the model version string (e.g., "YOLO26s v4.0")

2. **ml-detector reads VERSION at startup**:
   - `load_model_version()` reads VERSION file when model loads
   - `/health` endpoint returns `model_version` field
   - `/detect` responses include dynamic `model_version`

3. **Coordinator uses ml-detector's version**: Falls back to "unknown" if not provided (but ml-detector always provides it now)

4. **Backend re-detection labels itself**: Shows as "YOLO26s v4.0 PyTorch (backend)" to distinguish from ml-detector

**Files Changed**:
- `ml-detector/ml_detector_service.py` — reads VERSION, returns model_version in responses
- `coordinator/coordinator_service.py` — uses ml-detector's version (no hardcoded fallback)
- `backend/main.py` — `get_model_version()` helper for re-detection labeling
- `.github/copilot-instructions.md` — documented new deployment process

---

## ✅ 1. Auto-Update Model Registry

**Implemented**: `scripts/update_registry.py`

After deployment, the pipeline automatically:
- Reads the training summary JSON
- Appends a new model entry to `models/registry.json`
- Retires the previous production model
- Updates the VERSION file
- Adds deployment history entry

**Integrated**: Called automatically by `train_pipeline.sh` Step 4 after deploying.

---

## ✅ 2. Model Comparison Before Deploy

**Implemented**: `scripts/compare_before_deploy.py`

Before deploying, the pipeline:
- Runs `model.val()` on both new and current models using the test split
- Prints a side-by-side comparison table with deltas
- In `--strict` mode, aborts if new model mAP50 < current

**Integrated**: Called automatically by `train_pipeline.sh` Step 3 (before deploy). Use `--strict` flag to abort on regression.

---

## ✅ 3. Fix Hardcoded Dataset Version

**Implemented**: In `scripts/train_yolo26s_v2.py`

Dataset version is now parsed from the data.yaml path:
```python
ds_match = re.search(r'/v(\d+\.\d+)_', data_yaml)
dataset_version = ds_match.group(1) if ds_match else 'unknown'
```

---

## ✅ 4. Training Completion Notification

**Implemented**: ntfy.sh integration in `train_pipeline.sh`

```bash
bash scripts/train_pipeline.sh --notify deer-training
```

Sends a push notification via ntfy.sh when the pipeline completes, including mAP50 score and deploy status. Install the ntfy app on your phone and subscribe to your chosen topic.

---

## ✅ 5. Checkpoint Resume Support

**Implemented**: `--resume` flag in both `train_pipeline.sh` and `train_yolo26s_v2.py`

```bash
# Resume from a Phase 1 or Phase 2 checkpoint:
bash scripts/train_pipeline.sh --resume /path/to/checkpoint.pt --skip-export
```

When resuming:
- Phase 1 (frozen backbone) is skipped entirely
- Phase 2 starts from the provided checkpoint
- Dataset export is auto-skipped (uses latest existing dataset)

---

## ✅ 6. Automatic Rollback Script

**Implemented**: `scripts/rollback_model.py`

```bash
python3 scripts/rollback_model.py --list           # Show available backups
python3 scripts/rollback_model.py --to 20260411     # Restore specific backup
python3 scripts/rollback_model.py --to v3.0         # Match by version string
python3 scripts/rollback_model.py --to v3.0 --no-restart  # Don't restart container
```

Features:
- Lists all backups with size and modification date
- Saves current model as `pre_rollback_*` before overwriting
- Updates VERSION file with rollback label
- Restarts ml-detector container automatically

---

## Pipeline v3.0 Overview

The full pipeline now runs 4 steps:

```
Step 1: Export dataset (export_dataset_v3.py)
Step 2: Train YOLO26s  (train_yolo26s_v2.py)
Step 3: Compare models (compare_before_deploy.py)  ← NEW
Step 4: Deploy + register (deploy + update_registry.py) ← NEW
        + ntfy notification                              ← NEW
```

### Full Usage

```bash
# Standard full run with notification:
bash scripts/train_pipeline.sh --notify deer-training

# Strict mode (abort if regression):
bash scripts/train_pipeline.sh --strict --notify deer-training

# Resume after crash:
bash scripts/train_pipeline.sh --resume runs/train/deer_v2_20260411_phase2/weights/last.pt

# Train only, don't deploy:
bash scripts/train_pipeline.sh --skip-deploy

# Rollback if something goes wrong:
python3 scripts/rollback_model.py --list
python3 scripts/rollback_model.py --to 20260411
```

---

## Post-v4.0 Checklist

- [x] Verify test metrics (mAP50=0.883 > 0.855 ✓)
- [x] Confirm model deployed and ml-detector healthy
- [x] Update `models/registry.json` with v4.0 entry
- [x] Implement VERSION file approach (no more hardcoded versions)
- [x] Implement all 6 pipeline improvements
- [x] Integrate into train_pipeline.sh v3.0
- [x] Commit and push updates
