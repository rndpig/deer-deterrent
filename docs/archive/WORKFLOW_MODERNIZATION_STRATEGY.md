# Workflow Modernization Strategy
## Executive Summary

**Goal**: Transition from fragmented workflow (local server + Firebase UI + manual Colab training) to unified, cloud-integrated system with YOLO26 and automated GPU training.

**System Specs (Dell Server)**:
- CPU: Intel Core i7-4790 @ 3.60GHz (4 cores, 8 threads, Haswell architecture, 2013)
- This is **ideal for OpenVINO optimization** (supports AVX2, good INT8 performance)

## Critical Strategic Decision: Cloud GPU Training Integration

### Current Problem
- Manual Google Colab workflow (disconnected from production)
- No version control between training → deployment
- T4 GPU access requires manual intervention
- Dataset management is fragmented

### Recommended Solution: Google Cloud Vertex AI (Firebase Integration)

**Why Vertex AI?**
1. **Already using Firebase** → Same Google Cloud project, unified billing
2. **Serverless GPU training** → No VM management, pay only for training time
3. **Native Python SDK** → Trigger training jobs from local scripts
4. **Model Registry** → Built-in versioning and deployment
5. **Cost-effective** → T4 GPU: ~$0.35/hour, A100: ~$3/hour (only during training)

**Architecture Overview**:
```
┌─────────────────────────────────────────────────────────────┐
│                    Development Workflow                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Local Dell Server                                           │
│  ├─ Dataset Versioning (data/training_datasets/)            │
│  ├─ Model Registry (models/registry.json)                   │
│  ├─ Training Script Preparation                             │
│  └─ Trigger Vertex AI Training Job                          │
│                   ↓                                          │
│  Google Cloud Vertex AI                                      │
│  ├─ Spin up GPU instance (T4/V100/A100)                     │
│  ├─ Pull dataset from Cloud Storage                         │
│  ├─ Train YOLO26 model                                      │
│  ├─ Upload trained model to Cloud Storage                   │
│  └─ Terminate GPU instance                                  │
│                   ↓                                          │
│  Dell Server (Deployment)                                    │
│  ├─ Download trained model                                  │
│  ├─ Convert to OpenVINO INT8                                │
│  ├─ Update ML detector service                              │
│  └─ Validate performance                                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Dual-System Development Strategy

### Phase 1: Parallel Infrastructure (Weeks 1-2)
**Goal**: Build new system alongside existing, no disruption

**Tasks**:
1. **Dataset Versioning System** (local)
   - Create `data/training_datasets/v1.0_baseline/`
   - Export current deer snapshots
   - Generate manifest.csv with metadata
   
2. **Model Registry** (local)
   - Create `models/registry.json`
   - Document current YOLOv8 model (best.pt)
   - Track metrics and dataset version

3. **Cloud Setup** (Firebase/GCP)
   - Enable Vertex AI in Firebase project
   - Create Cloud Storage bucket for datasets/models
   - Set up service account credentials

**Existing System**: Continues running unchanged

---

### Phase 2: YOLO26 Training Pipeline (Week 3-4)
**Goal**: Establish cloud GPU training workflow

**Tasks**:
1. **Training Script** (`src/training/train_yolo26.py`)
   - Load dataset from versioned directory
   - Train YOLO26n on current dataset
   - Log metrics to registry
   - Support local testing OR Vertex AI execution

2. **Vertex AI Integration** (`src/training/vertex_trainer.py`)
   - Submit training job to Vertex AI
   - Monitor job status
   - Download trained model
   - Update registry

3. **First YOLO26 Model**
   - Train YOLO26n on existing dataset
   - Benchmark: YOLOv8 vs YOLO26 (accuracy + speed)
   - Document results in registry

**Existing System**: Still running with best.pt

---

### Phase 3: CPU Optimization & Testing (Week 5-6)
**Goal**: Optimize YOLO26 for i7-4790 CPU

**Tasks**:
1. **OpenVINO INT8 Conversion**
   - Export YOLO26n → ONNX → OpenVINO IR
   - Quantize to INT8 with calibration dataset
   - Target: 15-30ms inference on i7-4790

2. **Performance Validation**
   - Benchmark INT8 vs FP32 vs PyTorch
   - Validate accuracy (ensure <2% mAP drop)
   - Test on real Ring snapshots

3. **A/B Testing Framework**
   - Run both models side-by-side
   - Compare detection quality
   - Monitor false positive rates

**Existing System**: Running, new model runs in parallel for validation

---

### Phase 4: Gradual Deployment (Week 7-8)
**Goal**: Seamless transition to YOLO26

**Tasks**:
1. **Feature Flag Deployment**
   - Add `use_yolo26` setting in backend
   - Toggle between best.pt (YOLOv8) and yolo26_optimized.xml (OpenVINO)
   - Enable on 10% traffic initially

2. **Monitoring & Rollback**
   - Track inference latency
   - Monitor detection accuracy
   - Automatic rollback if errors

3. **Full Cutover**
   - Gradual increase: 10% → 50% → 100%
   - Retire best.pt when validated
   - Update documentation

**New System**: YOLO26 + OpenVINO INT8 in production

---

### Phase 5: Continuous Training Loop (Month 2+)
**Goal**: Automate quarterly retraining

**Tasks**:
1. **Active Learning Queue**
   - Tag high-value snapshots for training
   - Build review UI in dashboard
   - Auto-accumulate diverse examples

2. **Automated Retraining**
   - Cron job: Check queue every 4-6 months
   - If threshold met: Trigger Vertex AI training
   - Auto-deploy if metrics improve

3. **Dataset Growth**
   - Add new deer snapshots continuously
   - Track seasonal/weather diversity
   - Maintain train/val/test splits

---

## Storage Strategy

### Local Storage (Dell Server)
**Use for**:
- Active inference cache (recent snapshots)
- Current production models
- Development datasets (<10GB)

**Directory Structure**:
```
/home/rndpig/deer-deterrent/
├── data/
│   ├── training_datasets/
│   │   ├── v1.0_2026-01-baseline/
│   │   │   ├── images/
│   │   │   ├── labels/
│   │   │   └── manifest.csv
│   │   └── v1.1_2026-06-summer/
│   └── snapshots/  (rolling 30-day cache)
├── models/
│   ├── production/
│   │   ├── yolo26n_openvino_int8.xml  (active)
│   │   └── best.pt  (legacy)
│   └── registry.json
```

### Cloud Storage (GCS via Firebase)
**Use for**:
- Long-term dataset archives (multi-year)
- Training job inputs/outputs
- Model backups and history

**Bucket Structure**:
```
gs://deer-deterrent-ml/
├── datasets/
│   ├── v1.0_2026-01-baseline.tar.gz
│   └── v1.1_2026-06-summer.tar.gz
├── models/
│   ├── yolo26n_v1_20260215.pt
│   └── yolo26n_v2_20260615.pt
└── training_logs/
```

**Cost Estimate**:
- 100GB dataset storage: $2.30/month
- Training (4 hours T4 GPU): $1.40/quarter
- Egress (model downloads): <$0.50/quarter
- **Total**: ~$3-4/month

### Alternative: AWS S3
If you prefer S3 (based on past success):
- Similar structure to GCS
- Use boto3 for integration
- Compatible with SageMaker if needed

**Recommendation**: Start with GCS (Firebase integration), can migrate to S3 later if needed.

---

## Training Workflow Detail

### Option 1: Vertex AI Custom Training (Recommended)

**Setup** (one-time):
```bash
# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Create service account
gcloud iam service-accounts create vertex-trainer \
    --display-name="YOLO26 Training Service"

# Grant permissions
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="serviceAccount:vertex-trainer@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
    --role="roles/aiplatform.user"
```

**Training Script** (`src/training/vertex_train.py`):
```python
from google.cloud import aiplatform
import yaml

def trigger_training(dataset_version, model_name):
    """Submit YOLO26 training job to Vertex AI"""
    
    aiplatform.init(project="your-firebase-project", location="us-central1")
    
    # Define custom training job
    job = aiplatform.CustomTrainingJob(
        display_name=f"yolo26-training-{model_name}",
        container_uri="ultralytics/ultralytics:latest-gpu",
        model_serving_container_image_uri="ultralytics/ultralytics:latest-cpu"
    )
    
    # Submit job with GPU
    model = job.run(
        args=[
            "yolo", "detect", "train",
            f"data={dataset_version}/data.yaml",
            "model=yolo26n.pt",
            "epochs=100",
            "imgsz=640",
            "device=0"
        ],
        replica_count=1,
        machine_type="n1-standard-4",
        accelerator_type="NVIDIA_TESLA_T4",
        accelerator_count=1
    )
    
    return model

# Usage
if __name__ == "__main__":
    model = trigger_training("v1.0_baseline", "yolo26n_v1")
    print(f"Training complete: {model.resource_name}")
```

**Cost**: ~$0.35/hour × 4 hours = $1.40 per training run

### Option 2: Vertex AI Workbench (Interactive)
- Jupyter notebook environment with GPU
- Good for experimentation
- More expensive ($0.50-1.00/hour idle + GPU time)

### Option 3: Firebase Functions + Vertex AI (Fully Automated)
- Trigger training from dashboard UI
- Serverless function submits Vertex AI job
- Best for production automation

**Recommendation**: Start with Option 1 (script-based), migrate to Option 3 for full automation.

---

## Working with Existing System During Development

### Development Environment Separation

**Branch Strategy**:
```bash
main                    # Current production (YOLOv8)
├── feature/yolo26      # New training pipeline
└── feature/openvino    # CPU optimization
```

**Docker Isolation**:
```yaml
# docker-compose.dev.yml (for testing)
services:
  ml-detector-v2:
    image: ml-detector:yolo26
    ports:
      - "8002:8001"  # Different port
    environment:
      - MODEL_PATH=/app/models/yolo26n_openvino.xml
      - DEBUG=true

  ml-detector-v1:
    image: ml-detector:yolov8
    ports:
      - "8001:8001"  # Current production
    environment:
      - MODEL_PATH=/app/models/best.pt
```

**Testing Protocol**:
1. Run both models side-by-side
2. Send same snapshots to both
3. Compare results in logs
4. No impact on production coordinator

### Migration Checklist

**Pre-Migration** (Weeks 1-4):
- [ ] Dataset versioned and backed up to cloud
- [ ] YOLO26 trained and benchmarked
- [ ] OpenVINO INT8 conversion validated
- [ ] A/B testing shows ≥ equivalent accuracy
- [ ] Latency meets <50ms target

**Migration** (Week 5):
- [ ] Deploy YOLO26 model to test port
- [ ] Update ml-detector to support model switching
- [ ] Add feature flag to backend settings
- [ ] Enable for Side camera only (10% traffic)

**Validation** (Week 6):
- [ ] Monitor for 1 week: accuracy, latency, errors
- [ ] Compare false positive rates
- [ ] Validate deer detection recall

**Full Deployment** (Week 7):
- [ ] Gradually increase traffic: 25% → 50% → 100%
- [ ] Update documentation
- [ ] Archive YOLOv8 model as backup

**Rollback Plan**:
```python
# In backend settings
{
    "model_version": "yolo26_v1",  # or "yolov8_legacy"
    "rollback_available": true,
    "rollback_model": "models/production/best.pt"
}
```

---

## Implementation Roadmap

### Immediate (Next 7 Days)
1. **Dataset Versioning** (Day 1-2)
   - Export current deer snapshots
   - Create manifest with camera_id, timestamp, season
   - Backup to cloud storage

2. **Model Registry** (Day 2-3)
   - Document current YOLOv8 metrics
   - Create registry.json schema
   - Add Git integration

3. **Cloud Setup** (Day 3-5)
   - Enable Vertex AI in Firebase project
   - Create GCS bucket
   - Test training script locally

4. **First YOLO26 Training** (Day 5-7)
   - Train YOLO26n on existing dataset
   - Benchmark vs YOLOv8
   - Document results

### Short-Term (Weeks 2-4)
1. **Vertex AI Integration**
   - Submit first cloud training job
   - Validate end-to-end workflow
   - Document process

2. **OpenVINO Optimization**
   - Convert YOLO26n to INT8
   - Benchmark on i7-4790
   - Validate accuracy

3. **A/B Testing Framework**
   - Deploy both models in parallel
   - Compare on real snapshots
   - Build monitoring dashboard

### Medium-Term (Months 2-3)
1. **Production Deployment**
   - Gradual rollout with feature flags
   - Monitor and validate
   - Full cutover to YOLO26

2. **Active Learning Queue**
   - Add training_queue table
   - Build review UI
   - Auto-populate with detections

3. **Automated Retraining**
   - Quarterly training schedule
   - Auto-deploy if metrics improve
   - Alert on failures

---

## Cost Analysis

### Current System
- Dell server: Hardware already owned, $0/month compute
- Firebase Hosting: Free tier
- Manual labor: High (Colab management)

### New System (Estimated Monthly)
- Dell server: $0 (no change)
- Firebase Hosting: Free tier
- Cloud Storage (GCS): $2-3/month (100GB datasets)
- Vertex AI Training: $1.40/quarter ($0.47/month amortized)
- Monitoring/Logs: <$1/month

**Total New Cost**: ~$3-4/month
**Labor Savings**: Eliminates manual Colab workflow

---

## Next Steps (Immediate Action Items)

### 1. Query Current Dataset
Run this to assess dataset size:
```bash
ssh rndpig@192.168.7.215 '
cd /home/rndpig/deer-deterrent &&
find data -name "*.jpg" -o -name "*.png" | wc -l &&
du -sh data
'
```

### 2. Enable Vertex AI
```bash
# From your local machine
gcloud projects list  # Find Firebase project ID
gcloud config set project YOUR_PROJECT_ID
gcloud services enable aiplatform.googleapis.com
```

### 3. Create Dataset Version 1.0
```bash
# On Dell server
cd /home/rndpig/deer-deterrent
python3 scripts/create_dataset_version.py --version v1.0_baseline
```

### 4. First YOLO26 Training (Local Test)
```python
from ultralytics import YOLO

model = YOLO("yolo26n.pt")  # Download pretrained
model.train(
    data="data/training_datasets/v1.0_baseline/data.yaml",
    epochs=100,
    imgsz=640,
    device="cpu"  # For testing, use Vertex AI for real training
)
```

---

## Questions for You

1. **Firebase Project ID**: What's your current Firebase project ID? (for Vertex AI setup)
2. **Training Budget**: Comfortable with $1-2/quarter for GPU training? (very low cost)
3. **Urgency**: Timeline preference for migration? (I recommend 6-8 weeks for safety)
4. **Dataset Location**: Where is your 1-year annotated dataset currently? (you mentioned you have it)

---

## Summary

**Recommended Path Forward**:
1. ✅ Use YOLO26 (not YOLO11) - 43% faster CPU inference
2. ✅ Integrate Vertex AI via Firebase - no more manual Colab
3. ✅ Local storage + GCS backup - cost-effective, scalable
4. ✅ Parallel development - zero downtime migration
5. ✅ OpenVINO INT8 - optimized for i7-4790 CPU

**Timeline**: 6-8 weeks for complete migration, existing system runs unchanged throughout.

**Cost**: ~$3-4/month for cloud infrastructure, eliminates manual workflow.

Ready to proceed with Phase 1 implementation?
