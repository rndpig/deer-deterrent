# Training Pipeline Review & Improvement Plan

## Executive Summary

The current deer detection model (YOLOv8n) was trained on **258 manually annotated video frames** from Nov-Dec 2025 with **no custom image preprocessing**, minimal augmentation, and **no negative examples**. Production detections show confidence between 21-77% on clear deer images, with 2 of 10 detections at 0% (complete misses). The model frequently detects only a subset of deer present in frame.

**Root causes identified:**
1. Tiny training set (258 images) — well below the ~1,500-3,000+ recommended for single-class detection
2. Zero custom preprocessing for the challenging night-vision IR environment
3. No negative examples → unknown false positive rate
4. Annotation quality concerns (max IoU 0.334 between manual annotations and model predictions)
5. Camera bias — 430 frames from Driveway, 150 from Side, 0 from the camera (#10cea9e4511f) that actually sees deer in production
6. v1.1 pseudo-labels used same weak model at conf≥0.75, inheriting and amplifying existing errors

This document proposes a v2.0 training pipeline addressing each issue.

---

## 1. Current State Inventory

### 1.1 Deployed Model
| Property | Value |
|---|---|
| Architecture | YOLOv8n (C2f backbone, depth=0.33, width=0.25) |
| Classes | 1 ("deer") |
| File size | 6.2 MB (.pt), 4.8 MB (OpenVINO FP16) |
| Input size | 640×640 |
| Confidence threshold | 0.6 (backend), 0.75 (ml-detector container) |
| Hardware | Intel i7-4790 (Haswell, AVX2, 4C/8T) |

### 1.2 Training Data (v1.0)
| Source | Count | Notes |
|---|---|---|
| Video frames (total) | 1,218 | Across 18 uploaded videos |
| Frames selected for training | 560 | Subset of above |
| Frames with manual annotations | 258 | 484 bbox annotations, annotator="user" |
| Frames reviewed "correct" | 106 | Model-confirmed annotations |
| Frames reviewed "no_deer" | 135 | Verified negative frames |
| Annotation type | All "addition" | All manually drawn by user |

### 1.3 Available Untapped Data
| Source | Count | Notes |
|---|---|---|
| Ring event snapshots (no deer) | 252 | Pure negative examples with paths |
| Ring event snapshots (deer) | 10 | With detection bboxes from production |
| Unannotated videos #31-34 | 114 frames | Recent deer encounters, 0 annotations |
| All Ring events | 5,999 | 2.5 months of continuous monitoring |
| Cameras contributing deer | 1 of 4 | Only cam 10cea9e4511f (#3) |

### 1.4 Model Detection Statistics
| Confidence Range | Count | Notes |
|---|---|---|
| ≥ 0.8 | 270 | On video frames during extraction (biased — same training distribution) |
| 0.6–0.8 | 228 | |
| < 0.6 | 0 | Below threshold, filtered out |

### 1.5 Production Performance (Ring Deer Events)
| Event ID | Confidence | Issue |
|---|---|---|
| #26320 | 0.271 | 4-5 deer visible, only 2 detected |
| #26319 | 0.627 | |
| #26295 | 0.770 | Best result |
| #19699 | 0.522 | |
| #19697 | 0.522 | |
| #17365 | 0.468 | |
| #17363 | **0.000** | Complete miss — deer clearly visible |
| #17361 | **0.000** | Complete miss — deer clearly visible |
| #17359 | 0.310 | |
| #5766 | 0.215 | |

**Summary:** Only 1/10 above 0.75 threshold. 3/10 above 0.6. 2/10 are complete misses.

### 1.6 Current Preprocessing & Augmentation
- **Inference preprocessing:** None custom. Raw image → `model.predict()` (YOLO auto-sizes to 640×640)
- **Training preprocessing:** None. COCO→YOLO label format conversion only
- **Training augmentation:** YOLO built-in only (HSV jitter, horizontal flip, mosaic, scale/translate). No domain-specific augmentation for IR/night-vision

---

## 2. Diagnosis: Why the Model Underperforms

### 2.1 Insufficient Training Data
- **258 positives is far below** the recommended minimum (~1,500-3,000 for single-class YOLO). Ultralytics recommends ≥1,500 images per class for good results.
- Only 14 unique videos from 2 cameras (Driveway + Side). Real deer detections come from camera #10cea9e4511f which has **zero frames** in the training set.
- The model learned deer appearance from Nov-Dec Driveway/Side camera angles, not from the perspective where deer actually appear.

### 2.2 Domain Mismatch: IR Night Vision
- Ring cameras output IR (infrared) images at night — grayscale-ish with IR illumination artifacts
- Deer have natural camouflage that makes them blend into woodland backgrounds especially under IR
- The YOLO pretrained weights (COCO) learned object detection on daytime RGB images. The domain gap is significant
- **No CLAHE, histogram equalization, or contrast enhancement** is applied to help the model see deer against low-contrast backgrounds

### 2.3 Annotation Quality
- All 484 annotations are manual ("addition" type by "user") with no cross-validation
- Benchmark showed **max IoU of 0.334** between ground truth and model predictions — indicating either wrong annotations, wrong predictions, or both
- v1.1 pseudo-labels re-labeled with the same weak model at conf≥0.75, a classic "student = teacher" circular problem

### 2.4 No Negative Examples in Training
- The v1.0 dataset includes only frames with deer annotations (positives)
- 135 frames reviewed as "no_deer" were **not included** as negative examples
- This means the model was never explicitly trained on what a deer-free scene looks like from these cameras
- Result: unknown (and likely elevated) false positive rate on empty scenes

### 2.5 Camera Perspective Gap
- Training data cameras: Driveway (430 frames), Side (150 frames)
- Production deer camera: #10cea9e4511f — appears to be a different camera position with different angle, IR illumination, and background
- The model has literally never seen the viewpoint from which it's expected to detect deer

---

## 3. Improvement Plan: v2.0 Training Pipeline

### 3.1 Phase 1: Data Expansion & Curation (Estimated: 2-3 hours)

#### 3.1.1 Incorporate Production Deer Snapshots
- Extract all 10 Ring snapshots where `deer_detected=1` from the production camera
- These are the **highest value training images** — real deer from the exact camera angle used in production
- Even with detection bboxes of questionable quality, these images are critical

#### 3.1.2 Re-annotate with Assisted Labeling
Rather than trusting the current model's bboxes, use a **larger pretrained YOLO model** (YOLOv8m or YOLOv8l) as an annotation assistant:

```python
# Use a larger model for annotation (not the nano model we're trying to improve)
from ultralytics import YOLO
teacher = YOLO('yolov8m.pt')  # Medium model — much more accurate

# Run on all candidate images at low confidence threshold
results = teacher.predict(image, conf=0.15, classes=[0,1,2,3,...])
# Map COCO classes: 0=person(ignore), 14=bird(ignore), ...
# Check for large animal-shaped detections
```

However, COCO models detect "deer" only indirectly. Better approach:

**Option A: Manual re-annotation using CVAT/Label Studio**
- Install CVAT locally or use the online version
- Re-annotate all 258 existing positive frames + 10 production snapshots
- This fixes the IoU=0.334 annotation quality problem

**Option B: Semi-automated with MegaDetector**
- Microsoft's [MegaDetector](https://github.com/microsoft/CameraTraps) is specifically trained for wildlife camera trap images
- Classes: animal, person, vehicle — the "animal" class covers deer excellently
- Run MegaDetector on all images, use its bboxes as ground truth
- Confidence threshold ~0.3 for MegaDetector (it's calibrated differently)

**Recommendation: Option B (MegaDetector)** — it's purpose-built for exactly this use case (wildlife camera traps with IR images).

#### 3.1.3 Add Negative Examples
- Include **252 Ring snapshots** where no deer were detected as negative training images (empty label files)
- Include the **135 reviewed "no_deer" video frames** as additional negatives
- Target ratio: ~40% negative examples (industry standard for detection tasks)

#### 3.1.4 Incorporate Unannotated Videos #31-34
- Videos 31-34 have 114 frames with deer from recent encounters
- These contain 60 detections but 0 annotations → annotate these first
- Particularly valuable because they're recent and from the production environment

#### 3.1.5 Target Dataset Composition (v2.0)
| Category | Source | Count | Status |
|---|---|---|---|
| Positive (annotated video frames) | Existing v1.0 | ~258 | Re-annotate with MegaDetector |
| Positive (production snapshots) | Ring deer events | 10 | Annotate with MegaDetector |
| Positive (new videos #31-34) | Unannotated frames | ~114 | Annotate with MegaDetector |
| Hard negatives (no-deer review) | Video frames | 135 | Ready (empty labels) |
| Negative (Ring snapshots) | No-deer events | 252 | Ready (empty labels) |
| **Total** | | **~769** | **~382 positive, ~387 negative** |

This is 3x the current dataset size, but still below the 1,500+ recommended. See Phase 3 for augmentation-based expansion.

### 3.2 Phase 2: Image Preprocessing Pipeline (Estimated: 1-2 hours to implement)

Create a custom preprocessing pipeline optimized for IR/night-vision deer detection.

#### 3.2.1 CLAHE (Contrast Limited Adaptive Histogram Equalization)
The single most impactful preprocessing step for night-vision images:

```python
import cv2
import numpy as np

def enhance_ir_image(image: np.ndarray) -> np.ndarray:
    """Enhance IR/night-vision image for better deer visibility."""
    # Convert to LAB color space
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    
    # Apply CLAHE to luminance channel only
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced_l = clahe.apply(l_channel)
    
    # Merge and convert back
    enhanced_lab = cv2.merge([enhanced_l, a_channel, b_channel])
    enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
    
    return enhanced
```

**Why this works:** IR images from Ring cameras have narrow dynamic range, especially at night. Deer fur reflects IR differently than foliage, but the difference is subtle. CLAHE locally enhances contrast, making deer edges more distinct without blowing out bright areas (IR LEDs).

#### 3.2.2 Adaptive Denoising
IR cameras produce noise at night. Light denoising helps without destroying edges:

```python
def denoise_ir(image: np.ndarray) -> np.ndarray:
    """Light denoising for IR images — preserves edges."""
    return cv2.fastNlMeansDenoisingColored(image, None, h=6, hForColorComponents=6, 
                                            templateWindowSize=7, searchWindowSize=21)
```

#### 3.2.3 Edge Enhancement (Optional)
Can help the model detect deer contours against busy backgrounds:

```python
def enhance_edges(image: np.ndarray, alpha=1.5) -> np.ndarray:
    """Sharpen edges using unsharp masking."""
    blurred = cv2.GaussianBlur(image, (0, 0), 3)
    sharpened = cv2.addWeighted(image, alpha, blurred, 1 - alpha, 0)
    return sharpened
```

#### 3.2.4 Preprocessing Integration Points

**During Training Data Export:**
```python
# Apply preprocessing to ALL training images before export
for image_path in training_images:
    img = cv2.imread(str(image_path))
    img = enhance_ir_image(img)          # CLAHE
    # Optionally: img = denoise_ir(img)  # Denoise
    cv2.imwrite(str(output_path), img)
```

**During Inference (ml-detector container):**
```python
# In the /detect endpoint, add preprocessing before model.predict()
img_array = np.array(pil_image)
img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
img_array = enhance_ir_image(img_array)
results = model.predict(img_array, conf=threshold)
```

**Critical:** Preprocessing must be identical during training and inference. If you train with CLAHE, you must inference with CLAHE.

### 3.3 Phase 3: Advanced Augmentation Strategy (Estimated: 1 hour to configure)

Beyond YOLO's built-in augmentation, add domain-specific transforms using Albumentations:

```python
import albumentations as A

train_transform = A.Compose([
    # === IR/Night-Vision Specific ===
    A.CLAHE(clip_limit=4.0, tile_grid_size=(8, 8), p=0.5),     # Adaptive contrast
    A.RandomBrightnessContrast(
        brightness_limit=(-0.3, 0.3),    # Simulate varying IR illumination
        contrast_limit=(-0.2, 0.3),
        p=0.7
    ),
    A.RandomGamma(gamma_limit=(60, 140), p=0.5),               # IR sensor variation
    A.GaussNoise(var_limit=(10.0, 50.0), p=0.4),               # IR sensor noise
    A.GaussianBlur(blur_limit=(3, 5), p=0.2),                  # Slight defocus
    
    # === Geometric (complement YOLO built-in) ===
    A.RandomRotate90(p=0.0),             # Disabled — cameras are fixed orientation
    A.HorizontalFlip(p=0.5),            # Deer approach from both sides
    A.ShiftScaleRotate(
        shift_limit=0.1,
        scale_limit=0.2,
        rotate_limit=5,                  # Slight rotation only
        p=0.5
    ),
    
    # === Weather/Environment Simulation ===
    A.RandomFog(fog_coef_lower=0.1, fog_coef_upper=0.3, p=0.1),  # Misty conditions
    A.RandomShadow(p=0.2),                                        # Tree shadows
    
    # === Deer-Specific ===
    A.CoarseDropout(                     # Simulate partial occlusion (behind trees)
        max_holes=4, max_height=60, max_width=60,
        min_holes=1, min_height=20, min_width=20,
        fill_value=0, p=0.3
    ),
], bbox_params=A.BboxParams(format='yolo', label_fields=['class_labels']))
```

**Key insight:** Current augmentation completely ignores the IR domain. Adding brightness/contrast/gamma variation simulates the wide range of IR illumination conditions the camera encounters across nights and seasons.

#### 3.3.1 Offline Augmentation for Dataset Expansion
Since we're still below 1,500 images, generate augmented copies offline:

```python
# For each positive image, generate 3-4 augmented versions
# This expands ~382 positives to ~1,500+ training images
AUGMENTATION_FACTOR = 4  # Per positive image
```

Target: **~1,500 positives + ~400 negatives = ~1,900 total training images**

### 3.4 Phase 4: Training Configuration (Estimated: 2-4 hours GPU time on Colab T4)

#### 3.4.1 Model Architecture Decision

**Important context:** The project originally planned to use YOLO26 for its CPU-optimized architecture. However, what's actually deployed is a YOLOv8n labeled "YOLO26n v1.1" — the Dockerfile pins `ultralytics==8.3.0`, which predates the real YOLO26 release (Jan 14, 2026, requires `ultralytics>=8.4.0`). The deployment summary itself states "Architecture: YOLOv8n (YOLO26n v1.1)" — confirming it's YOLOv8n under a YOLO26 label.

| Option | Params | CPU Speed (i7-4790) | COCO mAP50-95 | Key Traits | Recommendation |
|---|---|---|---|---|---|
| YOLOv8n | 3.2M | ~56ms (OV FP16) | 37.3 | Current (mislabeled as YOLO26n) | ❌ Insufficient capacity |
| YOLOv8s | 11.2M | ~100ms (OV FP16 est) | 44.9 | Proven, more capacity | ⚠️ Viable fallback |
| YOLO26n | 2.4M | ~39ms (ONNX CPU) | 40.9 | NMS-free, DFL-free, 43% faster CPU | ⚠️ May still be too small |
| **YOLO26s** | **~9M** | **~60-80ms (OV FP16 est)** | **~46** | **NMS-free, CPU-optimized, more capacity** | **✅ Recommended** |
| YOLO26m | ~20M | ~150ms (OV FP16 est) | ~50 | High accuracy, slower | ⚠️ Only if needed |

**Recommendation: YOLO26s (small)**

Rationale:
- **YOLO26 was the right architectural choice all along** — NMS-free inference and DFL removal give it a native CPU speed advantage of ~43% over YOLOv8 at equivalent accuracy
- **The current "YOLO26n" is actually a mislabeled YOLOv8n** — we never actually deployed real YOLO26. Upgrading to genuine YOLO26 fixes this
- **YOLO26s over YOLO26n** because the nano variant (~2.4M params) likely doesn't have enough capacity for the subtle IR deer-vs-background discrimination. The "s" variant (~9M params) provides substantially more capacity while remaining fast on CPU
- **YOLO26s on OpenVINO FP16 should achieve ~60-80ms** on the i7-4790 — well within the 25-second snapshot interval
- **Simpler deployment** — YOLO26's NMS-free output `(1, 300, 6)` → `[x1, y1, x2, y2, confidence, class_id]` eliminates NMS post-processing entirely, which benefits OpenVINO export
- **INT8 quantization is cleaner** — no DFL module to quantize means less accuracy loss from INT8

**To use real YOLO26:** Update `ultralytics==8.3.0` → `ultralytics>=8.4.0` in Dockerfile.ml-detector

**Fallback:** If YOLO26s doesn't train well on this small dataset, YOLOv8s is the proven alternative with more community support

#### 3.4.2 Training Hyperparameters (v2.0)

```yaml
# configs/training_config_v2.yaml
model:
  architecture: "yolo26s"      # Real YOLO26 small (requires ultralytics>=8.4.0)
  pretrained: true              # Start from COCO-pretrained yolo26s.pt
  num_classes: 1
  fallback: "yolov8s"          # If YOLO26s doesn't converge well

training:
  epochs: 150                  # More epochs with early stopping
  batch_size: 16               # On Colab T4
  learning_rate: 0.01
  optimizer: "AdamW"           # Better than SGD for smaller datasets
  weight_decay: 0.0005
  warmup_epochs: 5
  patience: 30                 # Early stopping
  
  # Learning rate schedule
  lr_scheduler: "cosine"       # Cosine annealing
  lrf: 0.01                   # Final LR = lr0 * lrf
  
  # Device — Google Colab T4 GPU (see Section 3.4.4)
  device: "cuda"               # Colab T4
  workers: 2

augmentation:
  # YOLO built-in (on top of Albumentations offline augmentation)
  hsv_h: 0.02                 # Slight increase for IR variation
  hsv_s: 0.7
  hsv_v: 0.5                  # Increased — IR brightness varies a lot
  translate: 0.15
  scale: 0.5
  fliplr: 0.5
  mosaic: 1.0
  mixup: 0.15                 # Enable—helps with generalization
  copy_paste: 0.1             # Copy deer to different backgrounds

validation:
  conf_threshold: 0.001       # Low for mAP calculation
  iou_threshold: 0.6
```

#### 3.4.3 Transfer Learning Strategy
COCO pretrained weights are RGB-daytime, but retain useful low-level feature extractors (edges, textures) that transfer well to IR images:

1. **Start with COCO-pretrained YOLO26s** (yolo26s.pt — downloads automatically with `ultralytics>=8.4.0`)
2. **Freeze backbone layers for first 20 epochs** — let the head adapt to deer-specific features
3. **Unfreeze all layers for remaining epochs** — fine-tune the full network
4. This prevents catastrophic forgetting of useful low-level features while adapting to the IR domain

```python
from ultralytics import YOLO

# Requires: pip install ultralytics>=8.4.0
model = YOLO('yolo26s.pt')  # Downloads real YOLO26s pretrained weights

# Phase 1: Freeze backbone (20 epochs)
results1 = model.train(
    data='data.yaml',
    epochs=20,
    freeze=10,          # Freeze first 10 layers (backbone)
    lr0=0.01,
    optimizer='AdamW',
    imgsz=640,
    batch=16,
    device='cuda',      # Colab T4
)

# Phase 2: Full fine-tune (130 epochs)
results2 = model.train(
    data='data.yaml',
    epochs=130,
    freeze=0,           # Unfreeze all
    lr0=0.001,          # Lower LR for fine-tuning
    optimizer='AdamW',
    imgsz=640,
    batch=16,
    device='cuda',
)
```

#### 3.4.4 GPU Training Strategy

**Training hardware: Google Colab T4 GPU** (existing workflow, proven in v1.0 training)

The Dell i7-4790 server is CPU-only — ideal for **inference** (which is why YOLO26 + OpenVINO was chosen), but too slow for training. Training v1.0 took 14.3 hours on Colab T4. With the expanded v2.0 dataset (~1,900 images) and YOLO26s, expect ~4-8 hours on T4.

**Workflow:**
1. Prepare dataset locally (preprocessing, augmentation, splits)
2. Upload to Google Drive (shared folder already exists: "Deer video detection")
3. Open Colab notebook → connect T4 runtime
4. Train YOLO26s → download `best.pt`
5. Export to OpenVINO FP16 locally on the Dell server
6. Deploy to Docker containers

**Why not Vertex AI?** The WORKFLOW_MODERNIZATION_STRATEGY.md proposed Vertex AI for automated training. This is a good long-term goal, but for the immediate v2.0 retraining, Colab is simpler — no cloud billing setup, no service account configuration, and the free T4 tier is sufficient for this dataset size.

**Future:** Once the active learning pipeline (Section 7) generates enough data for regular retraining, automate via Vertex AI or Colab Pro scheduled notebooks.

### 3.5 Phase 5: Evaluation & Comparison Framework

#### 3.5.1 Metrics to Capture (Old vs New)

| Metric | How to Measure | What It Shows |
|---|---|---|
| **mAP@50** | `model.val()` on test set | Overall detection accuracy |
| **mAP@50:95** | `model.val()` on test set | Precision of bbox localization |
| **Precision @ prod threshold** | At conf=0.5 (proposed new threshold) | False positive rate |
| **Recall @ prod threshold** | At conf=0.5 | Miss rate |
| **Inference time (ms)** | Mean of 100 runs on i7-4790 | Real-time feasibility |
| **Production deer recall** | How many of the 10 known deer events are detected | Real-world effectiveness |
| **Production deer confidence** | Mean confidence on the 10 deer snapshots | Confidence calibration |
| **False positive rate** | Run on 252 negative Ring snapshots | Specificity |

#### 3.5.2 Holdout Test Set Design
**Critical:** The 10 production Ring deer snapshots must be **held out entirely** from training. They're the only real-world evaluation data we have.

```
Test set (untouchable):
├── 10 Ring deer snapshots (production camera)
├── 50 Ring negative snapshots (random from 252)
└── ~20% of annotated video frames (standard split)
```

#### 3.5.3 A/B Comparison Script

```python
# scripts/compare_models.py
models = {
    'v1.0_yolov8n': 'models/production/best.pt',
    'v2.0_yolov8s': 'models/v2.0/best.pt',
    'v2.0_yolov8s_openvino': 'models/v2.0/openvino/best_fp16.xml',
}

# Test on: production deer snapshots, negative snapshots, held-out frames
# Report: detection count, confidence, latency, mAP
```

---

## 4. OpenVINO / INT8 Assessment

### 4.1 Is OpenVINO FP16 Still Needed?
**Yes, and YOLO26 is even better for OpenVINO.** YOLO26's NMS-free architecture exports more cleanly to OpenVINO than YOLOv8 (no NMS post-processing layer to handle). With YOLO26s:

| Format | Estimated Inference (i7-4790) |
|---|---|
| YOLO26s PyTorch FP32 | ~150-200ms |
| YOLO26s OpenVINO FP16 | ~60-80ms |
| YOLO26s OpenVINO INT8 | ~30-50ms |

### 4.2 Is INT8 Quantization Needed?
**Not immediately.** At ~60-80ms with FP16, YOLO26s processes snapshots well within the 25-second polling interval. INT8 would be a "nice-to-have" optimization for later — focus first on getting a model that actually detects deer reliably.

**Recommendation:** Export to OpenVINO FP16 for deployment. YOLO26's DFL-free architecture makes future INT8 conversion cleaner when needed.

### 4.3 When to Revisit INT8
- If snapshot polling frequency increases to < 5 seconds
- If running all 4 cameras simultaneously requires batching
- If switching to YOLO26m for higher accuracy (would need INT8 to stay under 100ms)

---

## 5. Implementation Roadmap

### Step 1: Set Up Annotation Environment (~30 min)
```bash
# Install MegaDetector for annotation assistance
pip install megadetector

# Or use CVAT for manual annotation
# docker run -p 8080:8080 cvat/server
```

### Step 2: Export All Candidate Images from Server (~15 min)
```python
# scripts/export_training_candidates_v2.py
# Exports: 
#   - 258 existing annotated frames (images only)
#   - 10 Ring deer snapshots
#   - 114 frames from videos #31-34
#   - 252 negative Ring snapshots  
#   - 135 no-deer reviewed frames
```

### Step 3: Run MegaDetector Annotation (~1 hour)
```python
# scripts/annotate_with_megadetector.py
# Run MegaDetector on all positive candidate images
# Generate YOLO-format labels
# Manual review pass: spot-check 10% for quality
```

### Step 4: Build v2.0 Dataset (~30 min)
```python
# scripts/build_dataset_v2.py
# 1. Apply CLAHE preprocessing to all images
# 2. Generate augmented copies (4× for positives)  
# 3. Create train/val/test splits (hold out Ring deer snapshots for test)
# 4. Write data.yaml
```

### Step 5: Train YOLO26s on Colab T4 (~4-8 hours)
```python
# notebooks/train_deer_v2_colab.ipynb
# 1. pip install ultralytics>=8.4.0  (required for real YOLO26)
# 2. Upload dataset to Google Drive
# 3. Train YOLO26s: model = YOLO('yolo26s.pt'); model.train(data=...)
# 4. Evaluate on test set
# 5. Download best.pt
```

### Step 6: Benchmark & Compare (~30 min)
```python
# scripts/evaluate_v2.py
# Compare v1.0 (YOLOv8n mislabeled YOLO26n) vs v2.0 (real YOLO26s) on:
#   - 10 Ring deer snapshots (held-out)
#   - 252 Ring negative snapshots
#   - Inference latency on i7-4790
```

### Step 7: Export & Deploy (~15 min)
```bash
# Update ultralytics in Dockerfile.ml-detector: ultralytics>=8.4.0
# Export to OpenVINO FP16
yolo export model=models/v2.0/best.pt format=openvino half=True imgsz=640

# Integrate CLAHE preprocessing into ml-detector container
# Update Dockerfile.ml-detector with preprocessing step

# Deploy
docker-compose down && docker-compose up -d
```

---

## 6. Confidence Threshold Recommendation

The current 0.6/0.75 thresholds are too high for the current model and likely also too high initially for v2.0.

**Proposed approach:**
1. Train v2.0 model
2. Plot precision-recall curve on the held-out test set
3. Choose threshold at the **knee of the PR curve** where recall is ≥ 0.9
4. Expected: threshold ~0.3-0.5 initially, increasing as model improves with more data

**For deployment, use a two-tier threshold:**
- **Alert threshold (0.3):** Record the detection, store bbox, mark for review
- **Confirmed threshold (0.6):** Trigger deterrent action automatically

This captures more true positives for training feedback while avoiding false-positive deterrent activations.

---

## 7. Long-Term Data Flywheel

The biggest improvement will come from continuous data collection:

```
Production detection → User confirms/denies → New training example
                                                    ↓
                                              Next model version
                                                    ↓
                                            Better detections  →  cycle continues
```

### 7.1 Active Learning Pipeline (Future)
1. Model detects something at confidence 0.3-0.6 (uncertain)
2. Dashboard shows it for user review
3. User clicks "yes-deer" or "no-deer"
4. Image + label automatically added to training pool
5. Retrain periodically (weekly? monthly?)

This is the most scalable path to a robust model. Every deer encounter improves the next model.

---

## 8. Negative Image Archiving Pipeline

### 8.1 The Problem
We can't easily get more deer images until they appear naturally across seasons. But we **can** continuously collect background/negative images from all cameras. These are critical for:
- Reducing false positives (model learns what "no deer" looks like from every angle)
- Capturing seasonal variation (lighting, foliage, snow, rain)
- Building a diverse background set that covers the full year

### 8.2 Current State
| Setting | Value | Issue |
|---|---|---|
| `ENABLE_PERIODIC_SNAPSHOTS` | `true` | ✅ Working |
| `PERIODIC_SNAPSHOT_CAMERAS` | `10cea9e4511f,587a624d3fae` | ⚠️ Only 2 of 4 cameras |
| Cleanup behavior | Deletes periodic files after 48h if no deer | ❌ **Losing training data** |
| `auto_archive_old_snapshots()` | Marks `archived=1` after 3 days | DB entries survive but files deleted |
| Snapshots on disk | 164 files (162 from cam 10cea9e4511f) | Very few survived cleanup |

### 8.3 Required Changes

#### Change 1: Add All 4 Cameras to Periodic Snapshot Polling
```
# docker-compose.yml environment:
PERIODIC_SNAPSHOT_CAMERAS=10cea9e4511f,587a624d3fae,4439c4de7a79,f045dae9383a
```

Camera inventory:
| Camera ID | Name | Events | Role |
|---|---|---|---|
| `10cea9e4511f` | Side (deer camera) | 1,273 | Primary — all deer detections come from here |
| `587a624d3fae` | (unknown) | 2,080 | Background/negative |
| `4439c4de7a79` | (unknown) | 1,395 | Background/negative |
| `f045dae9383a` | (unknown) | 1,251 | Background/negative |

#### Change 2: Archive Negative Snapshots Instead of Deleting
Modify the cleanup task to **move** snapshots to a training archive instead of deleting them, sampling at a sustainable rate:

```python
# New behavior in cleanup_no_deer_snapshots():
# 1. Keep 1 snapshot per camera per hour (instead of deleting all)
# 2. Move kept snapshots to data/training_archive/negatives/{camera_id}/
# 3. Delete the rest (to manage disk space)
# Target: ~24 images/camera/day × 4 cameras = ~96 negatives/day
# Over 1 year: ~35,000 negatives spanning all seasons/lighting
```

#### Change 3: Add Training Archive Directory Structure
```
backend/data/
├── snapshots/              # Live snapshots (rolling 48h window)
├── training_archive/       # Long-term training data collection
│   ├── negatives/          # Background images (no deer)
│   │   ├── 10cea9e4511f/   # Per-camera organization
│   │   ├── 587a624d3fae/
│   │   ├── 4439c4de7a79/
│   │   └── f045dae9383a/
│   └── positives/          # Confirmed deer images
│       └── (auto-collected from user "yes-deer" feedback)
```

#### Change 4: Disk Space Management
At ~40-50KB per JPEG snapshot:
- 96 images/day × 50KB = ~4.8 MB/day
- ~1.7 GB/year for negatives (very manageable on the Dell server)
- The Dell server has ample disk space for years of collection

### 8.4 Seasonal Collection Strategy

The real value of this archive is capturing **all four seasons** from all camera angles:

| Season | Months | Key Variations | Training Value |
|---|---|---|---|
| Winter | Dec-Feb | Snow, bare trees, short days, cold IR signature | ✅ Currently collecting (limited) |
| Spring | Mar-May | Budding foliage, rain, longer days, new growth | ❌ Not yet collected |
| Summer | Jun-Aug | Full foliage, hot IR background, longest days | ❌ Not yet collected |
| Fall | Sep-Nov | Leaf color change, falling leaves, deer rut season | ❌ Not yet collected |

**By February 2027**, we'll have a full year of background images across all seasons — enough to train a robust model that handles every environmental condition.

### 8.5 Positive Image Collection
Deer appearances are opportunistic, but the two-tier threshold (Section 6) means:
- Every detection at conf ≥ 0.3 gets saved (not just ≥ 0.6)
- User reviews uncertain detections on the dashboard
- Confirmed positives are automatically moved to `training_archive/positives/`
- Over a year, we'll accumulate far more than 10 deer images

---

## 9. Summary of Recommendations

| Priority | Action | Impact | Effort |
|---|---|---|---|
| **P0** | Re-annotate with MegaDetector | Fixes bbox quality (IoU=0.334 → IoU>0.7) | 1.5 hrs |
| **P0** | Add 252 negative examples | Reduces false positives | 15 min |
| **P0** | Add CLAHE preprocessing | Night-vision contrast for deer edges | 30 min |
| **P1** | Upgrade to real YOLO26s | NMS-free, CPU-optimized, ~9M params | Config change + ultralytics upgrade |
| **P1** | Annotate videos #31-34 | +114 recent frames from production camera | 1 hr |
| **P1** | Offline augmentation (4×) | Expands dataset to ~1,900 images | 30 min |
| **P1** | Train on Colab T4 with AdamW | Faster convergence, better generalization | 2-4 hrs |
| **P2** | Export to OpenVINO FP16 | Inference ~60-80ms on i7-4790 | 15 min |
| **P2** | Two-tier confidence threshold | More recall + safety against false triggers | 30 min |
| **P3** | Active learning pipeline | Continuous improvement from production | 2-3 hrs |
| **P3** | INT8 quantization | Further speed (not needed yet) | 1 hr |

**Estimated total effort for v2.0:** ~8-10 hours from start to deployed model

**Expected outcome:** Production deer recall from 30% (3/10 above threshold) → 80%+ (8/10 above threshold), with confidence on clear deer images > 0.7 instead of current 0.2-0.5.
