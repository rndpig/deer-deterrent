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

| Option | Params | Speed (i7-4790) | Accuracy | Recommendation |
|---|---|---|---|---|
| YOLOv8n | 3.2M | ~150ms (PT), ~60ms (OV FP16) | Low for this domain | ❌ Current — insufficient |
| **YOLOv8s** | **11.2M** | **~300ms (PT), ~100ms (OV FP16)** | **Good balance** | **✅ Recommended** |
| YOLOv8m | 25.9M | ~700ms (PT), ~200ms (OV FP16) | High | ⚠️ Too slow for real-time |
| YOLOv11n | 2.6M | ~140ms estimate | Similar to v8n | ❌ Same problem |
| YOLOv11s | 9.4M | ~280ms estimate | Slightly better than v8s | ⚠️ Consider if v8s insufficient |

**Recommendation: YOLOv8s (small)**

Rationale:
- **YOLOv8n is too small** for this domain. The nano model simply doesn't have enough capacity to learn the subtle IR features that distinguish deer from background foliage
- **YOLOv8s at ~100ms (OpenVINO FP16)** is well within the acceptable latency for Ring snapshot processing (snapshots arrive every ~30 seconds minimum)
- The jump from 3.2M → 11.2M parameters gives 3.5× more capacity for learning subtle IR texture patterns
- Still runs comfortably on the i7-4790 with OpenVINO

#### 3.4.2 Training Hyperparameters (v2.0)

```yaml
# configs/training_config_v2.yaml
model:
  architecture: "yolov8s"      # Upgrade from nano to small
  pretrained: true
  num_classes: 1

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
  
  # Device
  device: "cuda"               # Colab T4 mandatory
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
Instead of fine-tuning from COCO weights (which are RGB-daytime-biased):

1. **Start with COCO-pretrained YOLOv8s** (yolov8s.pt)
2. **Freeze backbone layers for first 20 epochs** — let the head adapt to deer-specific features
3. **Unfreeze all layers for remaining epochs** — fine-tune the full network
4. This prevents catastrophic forgetting of useful low-level features while adapting to the IR domain

```python
from ultralytics import YOLO

model = YOLO('yolov8s.pt')

# Phase 1: Freeze backbone (20 epochs)
results1 = model.train(
    data='data.yaml',
    epochs=20,
    freeze=10,          # Freeze first 10 layers (backbone)
    lr0=0.01,
    optimizer='AdamW',
    ...
)

# Phase 2: Full fine-tune (130 epochs)
results2 = model.train(
    data='data.yaml',
    epochs=130,
    freeze=0,           # Unfreeze all
    lr0=0.001,          # Lower LR for fine-tuning
    ...
)
```

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
**Yes, but for YOLOv8s, not YOLOv8n.** The current FP16 model exists but the base model (YOLOv8n) is too weak regardless of format. With YOLOv8s:

| Format | Estimated Inference (i7-4790) |
|---|---|
| YOLOv8s PyTorch FP32 | ~300-400ms |
| YOLOv8s OpenVINO FP16 | ~100-150ms |
| YOLOv8s OpenVINO INT8 | ~50-80ms |

### 4.2 Is INT8 Quantization Needed?
**Not immediately.** At ~100-150ms with FP16, the model processes snapshots well within the ~30-second arrival interval. INT8 would be a "nice-to-have" optimization for later — focus first on getting a model that actually detects deer reliably.

**Recommendation:** Export to OpenVINO FP16 for deployment. Defer INT8 to Phase 6 if latency becomes a concern with higher snapshot frequency.

### 4.3 When to Revisit INT8
- If snapshot polling frequency increases to < 5 seconds
- If running multiple cameras simultaneously requires batching
- If the user wants to run YOLOv8m (which would need INT8 to hit acceptable latency)

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

### Step 5: Train on Colab T4 (~2-4 hours)
```python
# notebooks/train_deer_v2_colab.ipynb
# 1. Upload dataset to Google Drive
# 2. Train YOLOv8s with config_v2.yaml
# 3. Evaluate on test set
# 4. Download best.pt
```

### Step 6: Benchmark & Compare (~30 min)
```python
# scripts/evaluate_v2.py
# Compare v1.0 (YOLOv8n) vs v2.0 (YOLOv8s) on:
#   - 10 Ring deer snapshots (held-out)
#   - 252 Ring negative snapshots
#   - Inference latency on i7-4790
```

### Step 7: Export & Deploy (~15 min)
```bash
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

## 8. Summary of Recommendations

| Priority | Action | Impact | Effort |
|---|---|---|---|
| **P0** | Re-annotate with MegaDetector | Fixes bbox quality (IoU=0.334 → IoU>0.7) | 1.5 hrs |
| **P0** | Add 252 negative examples | Reduces false positives | 15 min |
| **P0** | Add CLAHE preprocessing | Night-vision contrast for deer edges | 30 min |
| **P1** | Upgrade YOLOv8n → YOLOv8s | 3.5× more model capacity | Config change |
| **P1** | Annotate videos #31-34 | +114 recent frames from production camera | 1 hr |
| **P1** | Offline augmentation (4×) | Expands dataset to ~1,900 images | 30 min |
| **P1** | Train on Colab T4 with AdamW | Faster convergence, better generalization | 2-4 hrs |
| **P2** | Export to OpenVINO FP16 | Inference ~100-150ms on i7-4790 | 15 min |
| **P2** | Two-tier confidence threshold | More recall + safety against false triggers | 30 min |
| **P3** | Active learning pipeline | Continuous improvement from production | 2-3 hrs |
| **P3** | INT8 quantization | Further speed (not needed yet) | 1 hr |

**Estimated total effort for v2.0:** ~8-10 hours from start to deployed model

**Expected outcome:** Production deer recall from 30% (3/10 above threshold) → 80%+ (8/10 above threshold), with confidence on clear deer images > 0.7 instead of current 0.2-0.5.
