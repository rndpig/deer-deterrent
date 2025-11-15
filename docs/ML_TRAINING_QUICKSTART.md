# Automated ML Training Workflow - Quick Start

## Overview
This guide will get you started with the automated ML training workflow in under 30 minutes.

## Phase 1: Setup (15 minutes)

### Step 1: Google Drive API Setup
Follow the detailed guide: [GOOGLE_DRIVE_SETUP.md](./GOOGLE_DRIVE_SETUP.md)

**Quick checklist:**
- [ ] Create Google Cloud project
- [ ] Enable Google Drive API
- [ ] Create service account
- [ ] Download credentials JSON
- [ ] Share Drive folder with service account
- [ ] Add credentials to `configs/google-credentials.json`
- [ ] Update `.env` with folder ID

### Step 2: Install Dependencies
```bash
pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### Step 3: Test Connection
```bash
python scripts/test_drive_connection.py
```

You should see:
```
✓ Successfully connected to Google Drive
✓ Found X items in root folder
✓ Ready to sync training data
```

## Phase 2: Label Detections (Ongoing)

### 1. Load Demo Data (for testing)
1. Go to Dashboard
2. Click "💦 Live Mode - Load Demo"
3. Review the 15 synthetic detections

### 2. Review Detections (API)
```bash
# Mark detection as correct
curl -X POST http://localhost:8000/api/detections/det-0/review \
  -H "Content-Type: application/json" \
  -d '{"detection_id": "det-0", "review_type": "correct"}'

# Mark as false positive
curl -X POST http://localhost:8000/api/detections/det-1/review \
  -H "Content-Type: application/json" \
  -d '{"detection_id": "det-1", "review_type": "false_positive"}'

# Mark with corrected count
curl -X POST http://localhost:8000/api/detections/det-2/review \
  -H "Content-Type: application/json" \
  -d '{"detection_id": "det-2", "review_type": "incorrect_count", "corrected_deer_count": 2}'
```

### 3. Check Review Status
```bash
curl http://localhost:8000/api/detections/det-0/review
```

## Phase 3: Export & Sync (5 minutes)

### Export Training Data
```bash
curl -X GET http://localhost:8000/api/training/export
```

Returns:
```json
{
  "status": "success",
  "export_path": "temp/training_export/annotations_20241115_143022.json",
  "images_count": 10,
  "annotations_count": 15,
  "reviewed_detections": 10
}
```

### Sync to Google Drive
```bash
curl -X POST http://localhost:8000/api/training/sync-to-drive
```

Returns:
```json
{
  "status": "success",
  "message": "Training data synced to Google Drive",
  "version": "production_20241115_143022",
  "drive_folder_id": "1abc...xyz"
}
```

## Phase 4: Train Model (In Progress)

### Current Workflow:
1. Open Google Colab: `notebooks/train_deer_detector_colab.ipynb`
2. Run all cells
3. Download trained model
4. Deploy to server

### Automated Workflow (Coming Soon):
```bash
# Will trigger Colab training automatically
curl -X POST http://localhost:8000/api/training/trigger
```

## Phase 5: Deploy Model (Coming Soon)

```bash
# Will auto-download and deploy latest model
curl -X POST http://localhost:8000/api/training/deploy-latest
```

## API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/detections/{id}/review` | POST | Submit detection review |
| `/api/detections/{id}/review` | GET | Get review status |
| `/api/training/export` | GET | Export to COCO format |
| `/api/training/sync-to-drive` | POST | Sync to Google Drive |
| `/api/training/trigger` | POST | Trigger Colab training (soon) |
| `/api/training/deploy-latest` | POST | Deploy latest model (soon) |

## Review Types

| Type | Description | Use Case |
|------|-------------|----------|
| `correct` | Detection is accurate | Deer count and confidence are good |
| `false_positive` | No deer present | System detected deer when there weren't any |
| `incorrect_count` | Wrong deer count | System counted wrong number of deer |
| `missed_deer` | Deer not detected | Image has deer but system missed them |

## Next Steps

1. **This Week**: Review real detections as they come in
2. **Next Week**: Accumulate 50-100 reviewed detections
3. **Week 3**: First automated training run
4. **Week 4**: Deploy and test new model

## Troubleshooting

### "Google Drive not configured"
- Check `.env` file has correct credentials path and folder ID
- Run `python scripts/test_drive_connection.py` to verify

### "No reviewed detections to export"
- Review at least one detection with type `correct` or `incorrect_count`
- False positives are excluded from training data

### "Failed to sync to Drive"
- Check Google Drive API is enabled
- Verify service account has "Editor" permissions on folder
- Check credentials file is valid JSON

## Files Created

```
temp/training_export/
├── annotations_20241115_143022.json  # COCO format dataset
└── images/                           # Detection images (if available)

Google Drive: Deer video detection/
└── training_data/
    └── production_20241115_143022/
        ├── annotations_20241115_143022.json
        └── images/
```

## Full Workflow Diagram

```
┌─────────────────┐
│  Ring Cameras   │
└────────┬────────┘
         │ motion detected
         ↓
┌─────────────────┐
│  ML Detection   │  
└────────┬────────┘
         │ save with image
         ↓
┌─────────────────┐
│   Dashboard     │ ← Review detections
│ (Detection List)│    (correct/false positive)
└────────┬────────┘
         │ reviewed
         ↓
┌─────────────────┐
│  Export API     │ → temp/training_export/
└────────┬────────┘
         │ COCO format
         ↓
┌─────────────────┐
│  Drive Sync API │ → Google Drive
└────────┬────────┘
         │ auto-sync
         ↓
┌─────────────────┐
│  Google Colab   │ ← Train on GPU
│  (Automated)    │    (15-30 min)
└────────┬────────┘
         │ model ready
         ↓
┌─────────────────┐
│  Deploy API     │ → dilger-server
└────────┬────────┘
         │ restart service
         ↓
┌─────────────────┐
│  Production     │
│  (New Model)    │
└─────────────────┘
```

## Support

See full documentation:
- [ML_REFINEMENT_STRATEGY.md](./ML_REFINEMENT_STRATEGY.md) - Overall strategy
- [GOOGLE_DRIVE_SETUP.md](./GOOGLE_DRIVE_SETUP.md) - Drive API setup
- [notebooks/train_deer_detector_colab.ipynb](../notebooks/train_deer_detector_colab.ipynb) - Training notebook

Questions? Check the troubleshooting section or review the code in:
- `src/services/drive_sync.py` - Drive integration
- `backend/main.py` - API endpoints (search for `/api/training/`)
