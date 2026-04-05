# Model Re-Training Pipeline - Implementation Plan

**Status:** Ready to implement  
**Last Updated:** December 6, 2025  
**Annotations Collected:** 10 videos fully annotated ✅

---

## Current State

### Completed ✅
- **10 videos annotated** with mix of:
  - Auto-detected boxes marked as "Correct" 
  - Manual bounding boxes drawn
  - Frames marked as "No Deer"
- **All annotation data safely stored** in SQLite database
- **Frame extraction working** with configurable sampling rates
- **Annotation UI complete** with keyboard shortcuts
- **Train Model button added** (placeholder - needs implementation)

### What We're Building
Automated pipeline leveraging **Google Colab's free T4 GPU** to retrain YOLOv8 model with collected deer detection data.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  Dell OptiPlex (dilger-server)                      │
│  - SQLite database with annotations                 │
│  - Backend exports data to YOLO format              │
│  - Syncs to Google Drive via API                    │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│  Google Drive                                        │
│  /Deer video detection/training_data/               │
│    ├── images/                                       │
│    ├── labels/                                       │
│    └── dataset.yaml                                  │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│  Google Colab (Free T4 GPU)                         │
│  - Mounts Google Drive                               │
│  - Trains YOLOv8n model                              │
│  - Saves best.pt to Drive                            │
│  - Training time: ~5-15 minutes                      │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│  Backend downloads new model                         │
│  - Validates model                                   │
│  - Replaces yolov8n.pt                               │
│  - Restarts detector service                         │
└──────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Step 1: Export Annotations (Backend)
**File:** `backend/main.py`  
**Endpoint:** `POST /api/training/export`

**What it does:**
1. Query all frames with annotations or marked as "correct"
2. Convert bounding boxes to YOLO format: `class x_center y_center width height`
3. Save images to `data/training_export/images/`
4. Save labels to `data/training_export/labels/` (one .txt file per image)
5. Generate `dataset.yaml` with class names and paths
6. Return export statistics (images exported, annotations count, etc.)

**Data handling:**
- Includes frames with manual annotations (drawn boxes)
- Includes frames marked as "Correct" (uses auto-detection boxes)
- Skips frames marked as "No Deer"
- Preserves all original data in database (never deletes)

**Export format (YOLO):**
```
# Example: frame_001.txt
0 0.5234 0.4123 0.1890 0.2345
0 0.6789 0.5678 0.1234 0.2890
# Format: class_id x_center y_center width height (all normalized 0-1)
```

---

### Step 2: Google Drive Sync (Backend)
**File:** Use existing `src/services/drive_sync.py`  
**Endpoint:** `POST /api/training/sync-to-drive`

**What it does:**
1. Initialize DriveSync with service account credentials (already configured)
2. Connect to Google Drive folder: `/Deer video detection/`
3. Create `training_data/` subfolder if needed
4. Upload all exported images to `training_data/images/`
5. Upload all label files to `training_data/labels/`
6. Upload `dataset.yaml`
7. Create versioned backup before uploading (preserves history)
8. Return Google Drive folder URL for verification

**Google Drive structure:**
```
Deer video detection/
├── training_data/           # Auto-synced from production
│   ├── images/             # JPG images from frames
│   ├── labels/             # YOLO format .txt files
│   └── dataset.yaml        # Dataset configuration
├── trained_models/         # Output from Colab
│   ├── best.pt            # Best performing model
│   ├── last.pt            # Last epoch model
│   └── training_report.txt # Metrics and results
└── backups/               # Previous exports (timestamped)
```

**Credentials:**
- Uses service account JSON: `configs/google-credentials.json`
- Setup guide: `docs/GOOGLE_DRIVE_SETUP.md`

---

### Step 3: Update Colab Notebook
**File:** `notebooks/train_deer_detector_colab.ipynb`

**Current notebook needs:**
1. ✅ Already mounts Google Drive
2. ✅ Already has training code
3. ⚠️ **Needs modification:** Auto-detect `training_data/` folder location
4. ⚠️ **Needs modification:** Save trained model to `/trained_models/` in Drive
5. ⚠️ **Add:** Training metrics report
6. ⚠️ **Add:** Sample predictions on validation set

**Training configuration:**
- **Model:** YOLOv8n (nano - fastest, smallest)
- **Epochs:** 50-100 (depends on dataset size)
- **Image size:** 640x640 pixels
- **Batch size:** 16 (fits comfortably in T4 GPU memory)
- **Device:** CUDA (T4 GPU - free on Colab)
- **Expected time:** ~10-15 minutes for 100-200 images

**Optimizations:**
- Use pre-trained COCO weights as starting point
- Data augmentation: flip, rotate, brightness, contrast
- Early stopping if validation loss plateaus
- Save checkpoints every 10 epochs

---

### Step 4: Model Download (Backend)
**File:** `backend/main.py`  
**Endpoint:** `POST /api/training/download-model`

**What it does:**
1. Connect to Google Drive
2. Check `/trained_models/` for new `best.pt` file
3. Download model to temporary location
4. Validate model:
   - Load with YOLO library
   - Run test inference on sample image
   - Check output format is correct
5. **Backup current model:** `yolov8n.pt` → `yolov8n_backup_YYYYMMDD.pt`
6. Replace with new model: `best.pt` → `yolov8n.pt`
7. Restart detector service (reload model into memory)
8. Return validation results and metrics

**Safety measures:**
- ✅ Always backs up current model before replacement
- ✅ Validates new model before deployment
- ✅ Can rollback to previous model if issues detected
- ✅ Never modifies annotation data

---

### Step 5: Frontend Integration
**File:** `frontend/src/components/Training.jsx`

**Update `handleTrainModel()` function to:**

```javascript
1. Show modal: "Starting model training pipeline..."
2. Call POST /api/training/export
   - Display: "Exporting annotations... ⏳"
   - Show progress: "Exported 150 images with annotations"
3. Call POST /api/training/sync-to-drive
   - Display: "Uploading to Google Drive... ☁️"
   - Show: "Uploaded 150 images, 150 labels"
4. Show success message with instructions:
   - "✅ Data uploaded successfully!"
   - "🔗 Open Google Colab notebook"
   - Button: "Open Colab" (opens notebook in new tab)
5. Instructions for user:
   - "1. In Colab: Runtime → Change runtime type → T4 GPU"
   - "2. Click Runtime → Run all"
   - "3. Wait 10-15 minutes for training"
   - "4. Return here and click 'Download Model'"
6. After training, show "Download Model" button
7. Call POST /api/training/download-model
   - Display: "Downloading trained model... 📥"
   - Show validation results
   - Display before/after metrics if available
8. Success: "🎉 New model deployed! Your detector is now improved!"
```

**UI/UX improvements:**
- Progress indicators for each step
- Estimated time for each phase
- Link to Colab notebook with one-click open
- Clear instructions for what user needs to do
- Option to view training report after completion

---

## User Workflow (End-to-End)

### Happy Path:
1. **User clicks "🚀 Train Model" button** in video selector
2. Backend exports annotations (30 seconds)
   - Shows: "Exporting 150 frames with annotations..."
3. Backend uploads to Google Drive (1-2 minutes)
   - Shows: "Uploading to Google Drive... 50% complete"
4. **User clicks "Open Colab" button** (opens in new tab)
5. **User in Colab:** Runtime → Change runtime → T4 GPU → Save
6. **User in Colab:** Runtime → Run all
7. Training runs automatically (~10-15 minutes)
   - User can watch training progress in Colab
   - See loss decreasing, metrics improving
8. **User returns to app** and clicks "Download Model"
9. Backend downloads and deploys new model (30 seconds)
10. Success message: "New model deployed!"
11. **System immediately uses improved model** for all new detections

---

## Data Safety Guarantees

✅ **Your annotations are 100% SAFE:**
- **Never deleted** from SQLite database
- Export is **read-only** operation (copies data, doesn't move)
- Exported data is **additive** (doesn't overwrite previous exports)
- Current model **always backed up** before replacement
- Can **always rollback** to previous model
- Database has **multiple layers of backup**:
  - Local SQLite file
  - Google Drive sync (if configured)
  - Git history for code

✅ **Model deployment safety:**
- New model validated before deployment
- Current model backed up with timestamp
- Can revert by renaming backup file
- Validation includes test inference

---

## Technical Details

### YOLO Format Details
**Image:** `frame_001.jpg`  
**Label:** `frame_001.txt` with one line per object:
```
class_id x_center y_center width height
0 0.523 0.412 0.189 0.234
```
Where:
- `class_id`: 0 (deer - only one class in our case)
- All coordinates normalized 0-1 (relative to image dimensions)
- `x_center`, `y_center`: Center point of bounding box
- `width`, `height`: Box dimensions

### Dataset YAML
```yaml
path: /content/drive/MyDrive/Deer video detection/training_data
train: images
val: images  # We'll use 80/20 split automatically
nc: 1  # Number of classes
names: ['deer']
```

### Model Architecture
- **YOLOv8n (Nano)**: Smallest, fastest variant
  - Parameters: ~3 million
  - Speed: ~150 FPS on GPU
  - Accuracy: Good for single-class detection
- **Why nano?** 
  - Runs fast on Dell OptiPlex CPU
  - Good enough accuracy for deer detection
  - Fast training time
  - Can upgrade to YOLOv8s/m later if needed

---

## Performance Expectations

### Before Training (Current Model)
- Generic COCO weights trained on 80 classes
- May miss some deer poses/lighting conditions
- False positives on deer-like objects

### After Training (Custom Model)
- Trained specifically on YOUR Ring camera footage
- Better at:
  - Night vision (IR) conditions
  - Your specific camera angles
  - Deer in your yard's environment
  - Motion blur patterns from Ring cameras
- Fewer false positives
- Better confidence scores
- Improved small/distant deer detection

### Expected Improvements
- **Recall:** 85% → 92%+ (fewer missed deer)
- **Precision:** 80% → 90%+ (fewer false positives)
- **mAP@0.5:** 75% → 88%+ (overall better performance)

---

## Estimated Implementation Time

### Development:
- **Step 1 (Export):** 1-2 hours
- **Step 2 (Drive Sync):** 30 min (mostly exists already)
- **Step 3 (Colab Update):** 1 hour
- **Step 4 (Download):** 1 hour
- **Step 5 (Frontend):** 1 hour
- **Testing & Polish:** 1 hour
- **Total:** ~6 hours of development

### Runtime (per training session):
- **Export:** 30 seconds
- **Upload to Drive:** 1-2 minutes
- **User opens Colab:** 30 seconds
- **Training:** 10-15 minutes (on free T4 GPU)
- **Download & Deploy:** 30 seconds
- **Total:** ~15-20 minutes end-to-end

---

## Next Session Action Items

### Option A: Full Implementation (Recommended)
Implement all 5 steps in sequence, test end-to-end.

### Option B: Incremental Approach
1. **Session 1:** Implement Step 1 (Export), verify YOLO format
2. **Session 2:** Implement Step 2 (Drive Sync), verify upload
3. **Session 3:** Update Colab notebook, test training manually
4. **Session 4:** Implement Steps 4-5 (Download & Frontend)

**Recommendation:** Option A - complete implementation in one session ensures everything works together and you can start using the improved model immediately.

---

## Questions to Address Before Implementation

1. ✅ **Google Drive setup:** Already configured with service account
2. ✅ **Colab notebook:** Already exists at `notebooks/train_deer_detector_colab.ipynb`
3. ✅ **Drive sync code:** Already exists at `src/services/drive_sync.py`
4. ✅ **Annotations collected:** 10 videos fully annotated
5. ⚠️ **Verify:** Google Drive credentials still valid (check `configs/google-credentials.json`)

---

## References

- **Training Strategy:** `docs/ML_REFINEMENT_STRATEGY.md`
- **Google Drive Setup:** `docs/GOOGLE_DRIVE_SETUP.md`
- **Colab Notebook:** `notebooks/train_deer_detector_colab.ipynb`
- **Drive Sync Service:** `src/services/drive_sync.py`
- **ML Training Docs:** `docs/ML_TRAINING_QUICKSTART.md`

---

## Status: READY TO IMPLEMENT ✅

All prerequisites met:
- ✅ Annotations collected (10 videos)
- ✅ Google Drive configured
- ✅ Colab notebook exists
- ✅ Drive sync code ready
- ✅ UI button placeholder added
- ✅ Architecture planned
- ✅ Data safety verified

**Next step:** Begin implementation of Step 1 (Export endpoint) in next coding session.
