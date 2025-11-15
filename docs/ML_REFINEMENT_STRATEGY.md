# ML Model Refinement Strategy

## Current Workflow Issues
- Manual Google Colab workflow disconnected from production system
- Model training requires multiple manual steps
- Trained model must be manually downloaded and deployed
- No automated feedback loop from production detections to model improvement

## Proposed Solutions

### Option 1: Automated Colab Training Pipeline (RECOMMENDED)
**Leverage Google's free GPU while automating the workflow**

#### Architecture:
```
Production System (dilger-server)
    ↓ (export new labeled data)
Google Drive API
    ↓ (sync to drive)
Google Colab (scheduled notebook)
    ↓ (train on GPU)
GitHub Release / Backend API
    ↓ (auto-download)
Production System (auto-deploy)
```

#### Implementation:
1. **Data Collection Service** (on dilger-server)
   - Store all detection images with metadata
   - UI for reviewing/labeling false positives and missed detections
   - Export to COCO format periodically

2. **Google Drive Integration**
   - Use Google Drive API to auto-sync labeled data
   - Store in consistent folder structure

3. **Automated Colab Execution**
   - Use Colab's programmatic execution API
   - Trigger training runs via API call
   - OR use Google Cloud Functions + Cloud Scheduler

4. **Model Deployment Pipeline**
   - Colab saves trained model to Drive
   - Backend polls for new models or webhook notification
   - Auto-download and validate new model
   - Gradual rollout (test on subset first)

#### Pros:
- ✅ Free GPU access (15-20 GB RAM, T4 GPU)
- ✅ Fast training (minutes vs hours)
- ✅ Can automate entire pipeline
- ✅ Leverages existing Colab notebook
- ✅ Best of both worlds: local system + cloud GPU

#### Cons:
- ⚠️ Requires Google API setup
- ⚠️ Colab session limits (12-hour max)
- ⚠️ Some automation complexity

#### Estimated Implementation: 2-3 days

---

### Option 2: Local CPU Training
**Simple but slow - train on dilger-server CPU**

#### Implementation:
1. Add training script to backend
2. Store labeled data locally
3. Trigger training runs via API endpoint
4. Train overnight using CPU

#### Pros:
- ✅ Simple, no external dependencies
- ✅ Full control over training process
- ✅ Easy to integrate with production system

#### Cons:
- ❌ Very slow (hours vs minutes)
- ❌ CPU-only training inefficient
- ❌ Ties up server resources during training
- ❌ Limited to smaller models/datasets

#### Estimated Training Time:
- Small dataset (100 images): ~30-60 minutes
- Medium dataset (500 images): ~2-4 hours
- Large dataset (1000+ images): ~6-12 hours

#### Estimated Implementation: 4-6 hours

---

### Option 3: Cloud GPU Service (Paid)
**Use AWS/GCP/Azure GPU instances**

#### Options:
- **AWS SageMaker**: $0.05-0.50/hour (spot instances)
- **Google Cloud AI Platform**: $0.45-2.50/hour
- **Lambda Labs**: $0.50-1.10/hour (good for ML)
- **Vast.ai**: $0.20-0.80/hour (cheapest, less reliable)

#### Implementation:
1. Set up cloud GPU instance with auto-start/stop
2. Sync data via S3/GCS
3. Run training automatically
4. Deploy model back to production

#### Pros:
- ✅ Fast GPU training
- ✅ Scalable (can use bigger GPUs)
- ✅ No Colab session limits
- ✅ More reliable than free tier

#### Cons:
- ❌ Costs money (even if minimal)
- ❌ More infrastructure to manage
- ❌ Requires cloud account setup

#### Estimated Cost:
- Training 1x/week for 30 min: ~$5-10/month
- Training daily: ~$20-40/month

---

## Recommended Approach: Hybrid Automated Colab

### Phase 1: Data Collection (Week 1)
1. Add detection review UI to dashboard
2. Store all detections with images
3. Allow manual labeling: ✓ Correct / ✗ False Positive / + Missed Detection
4. Export labeled data to COCO format

### Phase 2: Google Drive Integration (Week 2)
1. Set up Google Drive API credentials
2. Create automated sync service
3. Upload new labeled data to Drive folder
4. Maintain dataset versioning

### Phase 3: Automated Training (Week 3)
1. Modify Colab notebook for programmatic execution
2. Set up webhook/API endpoint to trigger training
3. Implement model validation tests
4. Create auto-deployment script

### Phase 4: Continuous Improvement (Ongoing)
1. Monitor model performance metrics
2. Collect edge cases and failures
3. Retrain periodically (weekly/monthly)
4. A/B test new models before full deployment

---

## Quick Win: Manual Workflow Improvement

**While building automation, streamline the current manual process:**

### Create Training Helper Script
```bash
# scripts/prepare_training_data.sh
# 1. Export recent detections
# 2. Package for Drive upload
# 3. Generate instructions for Colab
# 4. After training, download and deploy model
```

### Add Model Deployment Script
```bash
# scripts/deploy_model.sh
# 1. Download model from Drive/Colab
# 2. Validate model (test on sample images)
# 3. Backup current model
# 4. Deploy new model
# 5. Restart ML service
```

**Reduces manual steps from 10+ to 2-3 commands**

---

## Code Samples

### 1. Detection Review UI Component
```python
# backend/main.py - Add review endpoint
@app.post("/api/detections/{detection_id}/review")
async def review_detection(
    detection_id: str,
    review: ReviewData  # correct, false_positive, missed_deer, confidence
):
    # Store review in database
    # Update training dataset
    # Return confirmation
```

### 2. Google Drive Sync Service
```python
# src/services/drive_sync.py
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

class DriveSync:
    def __init__(self, credentials_path):
        self.creds = Credentials.from_authorized_user_file(credentials_path)
        self.service = build('drive', 'v3', credentials=self.creds)
    
    def upload_training_data(self, local_path, drive_folder_id):
        # Package and upload labeled data
        # Maintain version history
```

### 3. Automated Colab Trigger
```python
# src/services/training_trigger.py
import requests

def trigger_colab_training(dataset_version):
    # Option A: Use Colab API (if available)
    # Option B: Use Cloud Function that executes notebook
    # Option C: Use GitHub Actions with Colab integration
```

---

## Next Steps

1. **Immediate**: Which approach interests you most?
2. **This Week**: Set up detection storage and review UI
3. **Next Sprint**: Implement chosen automation strategy

Would you like me to start implementing the detection review UI first? That's valuable regardless of which training approach you choose.
