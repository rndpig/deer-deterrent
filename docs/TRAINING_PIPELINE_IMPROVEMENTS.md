# Training Pipeline Improvements

**Created**: 2026-04-11  
**Updated**: 2026-04-11  
**Status**: v4.0 deployed, some improvements implemented

## Overview

These improvements were identified during the v4.0 training cycle.

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

**New Model Deployment Process**:
```bash
# 1. Copy model file
cp best.pt /home/rndpig/deer-deterrent/dell-deployment/models/production/

# 2. Update VERSION file
echo "YOLO26s v5.0" > /home/rndpig/deer-deterrent/dell-deployment/models/production/VERSION

# 3. Update registry.json with model metadata
# (manual for now, see Improvement #1 below)

# 4. Restart ml-detector
docker compose restart ml-detector

# No code changes required!
```

**Files Changed**:
- `ml-detector/ml_detector_service.py` — reads VERSION, returns model_version in responses
- `coordinator/coordinator_service.py` — uses ml-detector's version (no hardcoded fallback)
- `backend/main.py` — `get_model_version()` helper for re-detection labeling
- `.github/copilot-instructions.md` — documented new deployment process

---

## 1. Auto-Update Model Registry (High Priority)

**Problem**: After each training run, `models/registry.json` must be manually updated with the new model entry. This is easy to forget and leads to stale registry data.

**Solution**: Create `scripts/update_registry.py` that:
- Reads the training summary JSON (`runs/train/deer_v2_*_summary.json`)
- Extracts metrics, dataset version, architecture info
- Appends a new entry to `models/registry.json`
- Updates the previous production model's status to "retired"

**Integration**: Add to end of `train_pipeline.sh`:
```bash
python3 scripts/update_registry.py \
    --model "$BEST_MODEL" \
    --summary "$SUMMARY" \
    --dataset-dir "$DATASET_DIR"
```

**Effort**: ~50 lines of Python

---

## 2. Model Comparison Before Deploy (Medium Priority)

**Problem**: The pipeline deploys the new model without comparing it to the current production model. Could accidentally deploy a regression.

**Solution**: Before deploying, run validation on both models and compare:
```bash
# In train_pipeline.sh, before copying to production:
python3 scripts/compare_before_deploy.py \
    --new-model "$BEST_MODEL" \
    --current-model "$PRODUCTION_MODEL" \
    --data "$DATA_YAML"
```

Script should:
- Run `model.val()` on both models using the same test split
- Print side-by-side comparison table
- Warn (or abort with `--strict`) if new model mAP50 < current model

**Effort**: ~80 lines of Python

---

## 3. Fix Hardcoded Dataset Version (Low Priority)

**Problem**: In `train_yolo26s_v2.py`, the summary always says `"dataset_version": "2.0"` regardless of actual dataset.

**Location**: [scripts/train_yolo26s_v2.py](../scripts/train_yolo26s_v2.py) line ~270

**Fix**: Parse version from the data.yaml path (e.g., `/data/training_datasets/v3.0_20260411/data.yaml` → `"3.0"`):
```python
import re
match = re.search(r'/v(\d+\.\d+)_', data_yaml)
dataset_version = match.group(1) if match else 'unknown'
```

**Effort**: 5 lines

---

## 4. Training Completion Notification (Low Priority)

**Problem**: Training takes 10+ hours on CPU. Currently requires manual checking via SSH.

**Solution**: Add notification at end of `train_pipeline.sh`:

Option A - Simple webhook (ntfy.sh, Discord, Slack):
```bash
curl -X POST "https://ntfy.sh/deer-training" \
    -d "Training complete! mAP50=${MAP50}, deployed to production"
```

Option B - Email via sendmail:
```bash
echo "Training complete. See ${LOG_FILE}" | mail -s "Deer Training Done" owner@example.com
```

**Effort**: 5-10 lines in bash

---

## 5. Checkpoint Resume Support (Medium Priority)

**Problem**: If training crashes mid-Phase 2 (power outage, OOM, etc.), must restart from epoch 1.

**Solution**: Add `--resume` flag to both scripts:

In `train_pipeline.sh`:
```bash
--resume PATH    Resume from a checkpoint (skips export + phase1)
```

In `train_yolo26s_v2.py`:
```python
parser.add_argument("--resume", help="Path to checkpoint to resume from")

# Skip phase1 if resuming
if args.resume:
    phase1_best = Path(args.resume)
    phase1_epochs = 0
```

**Effort**: ~30 lines across both files

---

## 6. Automatic Rollback Script (Low Priority)

**Problem**: Pipeline creates backups (`best.pt.bak_YYYYMMDD_HHMMSS`) but there's no scripted way to rollback.

**Solution**: Create `scripts/rollback_model.py`:
```bash
python3 scripts/rollback_model.py --list          # Show available backups
python3 scripts/rollback_model.py --to 20260315   # Restore specific backup
```

Script should:
- List backups with dates and sizes
- Restore selected backup to `production/best.pt`
- Rebuild and restart ml-detector container
- Update registry.json deployment status

**Effort**: ~60 lines

---

## Implementation Order

1. **Fix hardcoded dataset version** — trivial, do first
2. **Auto-update registry** — most impactful for workflow
3. **Model comparison** — safety net before deploy
4. **Completion notification** — quality of life
5. **Resume support** — insurance for long runs
6. **Rollback script** — nice to have

---

## Post-v4.0 Checklist

After current training completes:
- [x] Verify test metrics (mAP50=0.883 > 0.855 ✓)
- [x] Confirm model deployed and ml-detector healthy
- [x] Update `models/registry.json` with v4.0 entry
- [x] Implement VERSION file approach (no more hardcoded versions)
- [ ] Implement improvements 1-2 from this list
- [x] Commit and push updates
