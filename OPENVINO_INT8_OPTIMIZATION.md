# OpenVINO INT8 Optimization Guide for YOLO26
## Optimized for Intel Core i7-4790 CPU

## System Specifications
**Dell Server CPU**: Intel Core i7-4790 @ 3.60GHz
- Architecture: Haswell (4th generation, 2013)
- Cores: 4 physical, 8 threads
- AVX2 Support: ✅ Yes (excellent for INT8 operations)
- Cache: 8MB L3
- **OpenVINO Support**: ✅ Fully supported, excellent INT8 performance

## Why OpenVINO INT8 for Your System

### Performance Gains (Expected)
Based on Ultralytics benchmarks and i7-4790 capabilities:

| Model Format | Inference Time | Speedup vs PyTorch |
|--------------|----------------|-------------------|
| PyTorch CPU (FP32) | ~150-200ms | 1x baseline |
| ONNX Runtime (FP32) | ~80-100ms | 1.8-2x |
| OpenVINO FP32 | ~60-80ms | 2.5-3x |
| **OpenVINO INT8** | **25-40ms** | **5-7x** |

**Your Target**: 25-40ms total inference (well under 50ms requirement!)

### Why INT8 Works Well on i7-4790
1. **AVX2 instructions** (introduced in Haswell) - native 8-bit integer operations
2. **4 cores** - good parallelization for batch operations
3. **High clock speed** (3.6GHz) - fast single-threaded performance
4. **OpenVINO optimization** - specifically tuned for Intel CPUs

### YOLO26 Advantages for INT8
- **No DFL module** - simpler architecture, better quantization
- **NMS-free inference** - eliminates post-processing bottleneck
- **Smaller model** - YOLO26n has only 5.4M parameters (vs YOLOv8n 3.2M)
- **Built for edge** - designed with quantization in mind

---

## Step-by-Step INT8 Conversion

### Prerequisites
```bash
# On Dell server
pip install ultralytics openvino openvino-dev
```

### Step 1: Export YOLO26 to OpenVINO FP32 (Baseline)
```python
from ultralytics import YOLO

# Load trained YOLO26 model
model = YOLO("models/production/yolo26n_trained.pt")

# Export to OpenVINO FP32 (no quantization)
model.export(
    format="openvino",
    imgsz=640,
    half=False,  # Keep FP32 for baseline
    dynamic=False,  # Fixed input size for better optimization
    batch=1  # Single image inference
)

# Output: yolo26n_trained_openvino_model/
#   ├── metadata.yaml
#   ├── yolo26n_trained.bin  (weights)
#   └── yolo26n_trained.xml  (network topology)
```

**Benchmark FP32**:
```python
import time
from ultralytics import YOLO

model = YOLO("models/production/yolo26n_trained_openvino_model/")

# Warm-up
for _ in range(10):
    model.predict("test_image.jpg", verbose=False)

# Benchmark
times = []
for i in range(100):
    start = time.time()
    results = model.predict("test_image.jpg", verbose=False, device="intel:cpu")
    times.append((time.time() - start) * 1000)

print(f"FP32 Inference Time: {sum(times)/len(times):.2f}ms ± {(max(times)-min(times))/2:.2f}ms")
```

Expected FP32 result: **60-80ms**

---

### Step 2: Export YOLO26 to OpenVINO INT8 (Quantized)

**Key Parameters**:
- `int8=True` - Enable INT8 quantization
- `data` - Path to calibration dataset (uses subset of training data)
- `fraction=0.5` - Use 50% of dataset for calibration (faster, still accurate)

```python
from ultralytics import YOLO

model = YOLO("models/production/yolo26n_trained.pt")

# Export to OpenVINO INT8 with calibration
model.export(
    format="openvino",
    imgsz=640,
    int8=True,  # Enable INT8 quantization
    data="data/training_datasets/v1.0_baseline/data.yaml",  # Calibration dataset
    fraction=0.5,  # Use 50% of data for calibration (faster)
    dynamic=False,
    batch=1,
    device="cpu"  # Quantization happens on CPU
)

# Output: yolo26n_trained_openvino_model/ (with INT8 quantized weights)
```

**What happens during export**:
1. Loads calibration dataset (50% of your deer training images)
2. Runs forward passes to collect activation statistics
3. Determines optimal INT8 quantization ranges per layer
4. Converts FP32 weights → INT8 weights (4x smaller)
5. Inserts quantization/dequantization ops where needed
6. Validates accuracy on calibration set

**Expected export time**: 5-10 minutes (depends on calibration dataset size)

---

### Step 3: Benchmark INT8 Model

```python
import time
from ultralytics import YOLO

# Load INT8 quantized model
model = YOLO("models/production/yolo26n_trained_openvino_model/")

# Warm-up (important for OpenVINO to optimize runtime)
print("Warming up...")
for _ in range(20):  # More warm-up for INT8
    model.predict("test_image.jpg", verbose=False, device="intel:cpu")

# Benchmark
print("Benchmarking...")
times = []
for i in range(100):
    start = time.time()
    results = model.predict("test_image.jpg", verbose=False, device="intel:cpu")
    times.append((time.time() - start) * 1000)

avg_time = sum(times) / len(times)
std_time = (max(times) - min(times)) / 2

print(f"INT8 Inference Time: {avg_time:.2f}ms ± {std_time:.2f}ms")
print(f"Min: {min(times):.2f}ms, Max: {max(times):.2f}ms")
```

**Expected INT8 result: 25-40ms** (5-7x speedup vs PyTorch!)

---

### Step 4: Validate Accuracy

**Critical**: Ensure INT8 quantization doesn't degrade deer detection accuracy

```python
from ultralytics import YOLO

# Load both models
fp32_model = YOLO("models/yolo26n_fp32_openvino_model/")
int8_model = YOLO("models/yolo26n_int8_openvino_model/")

# Validate on test set
print("Validating FP32 model...")
fp32_metrics = fp32_model.val(data="data/training_datasets/v1.0_baseline/data.yaml")

print("Validating INT8 model...")
int8_metrics = int8_model.val(data="data/training_datasets/v1.0_baseline/data.yaml")

# Compare metrics
print("\n=== Accuracy Comparison ===")
print(f"FP32 mAP50: {fp32_metrics.box.map50:.4f}")
print(f"INT8 mAP50: {int8_metrics.box.map50:.4f}")
print(f"Accuracy drop: {(fp32_metrics.box.map50 - int8_metrics.box.map50):.4f} ({((fp32_metrics.box.map50 - int8_metrics.box.map50) / fp32_metrics.box.map50 * 100):.2f}%)")

print(f"\nFP32 Precision: {fp32_metrics.box.p:.4f}")
print(f"INT8 Precision: {int8_metrics.box.p:.4f}")

print(f"\nFP32 Recall: {fp32_metrics.box.r:.4f}")
print(f"INT8 Recall: {int8_metrics.box.r:.4f}")
```

**Acceptable threshold**: <2% mAP drop (typically 0.5-1.5% for YOLO models)

---

## Advanced Optimization Techniques

### 1. ROI Cropping (Per-Camera Zones)
Reduce inference area to only relevant regions:

```python
# In configs/zones.yaml
cameras:
  Side_10cea9e4511f:
    roi:
      x: 0
      y: 200  # Skip top 200px (sky/trees)
      width: 1920
      height: 880  # Only ground-level area
    
  Driveway_587a624d3fae:
    roi:
      x: 400
      y: 300
      width: 1120  # Center focus area
      height: 780
```

**Benefit**: 20-30% faster inference (smaller input image)

### 2. Batch Size Tuning
Test batch inference for multiple snapshots:

```python
# Export with batch=4
model.export(format="openvino", int8=True, batch=4)

# Inference on 4 images at once
results = model.predict(["img1.jpg", "img2.jpg", "img3.jpg", "img4.jpg"])
```

**Benefit**: Better CPU utilization if processing queued snapshots

### 3. Thread Optimization
Configure OpenVINO threads for i7-4790:

```python
import openvino as ov

# Load model with custom thread config
core = ov.Core()
model = core.read_model("yolo26n_int8.xml")
compiled_model = core.compile_model(
    model,
    "CPU",
    config={
        "CPU_THREADS_NUM": "4",  # Match physical cores
        "CPU_BIND_THREAD": "YES",  # Pin threads to cores
        "CPU_THROUGHPUT_STREAMS": "1"  # Single stream for latency
    }
)
```

**Benefit**: 10-15% latency reduction

---

## Production Deployment

### Option 1: Using Ultralytics Wrapper (Simplest)
```python
from ultralytics import YOLO

class DetectorService:
    def __init__(self, model_path):
        self.model = YOLO(model_path)
        # Warm-up
        for _ in range(20):
            self.model.predict("dummy.jpg", verbose=False)
    
    def detect(self, image_path):
        results = self.model.predict(
            image_path,
            conf=0.75,  # Confidence threshold
            device="intel:cpu",
            verbose=False
        )
        return results[0]  # Single image result

# In ml-detector service
detector = DetectorService("models/production/yolo26n_int8_openvino_model/")
```

### Option 2: Native OpenVINO Runtime (Maximum Control)
```python
import openvino as ov
import cv2
import numpy as np

class OpenVINODetector:
    def __init__(self, model_path):
        self.core = ov.Core()
        self.model = self.core.read_model(model_path)
        self.compiled_model = self.core.compile_model(
            self.model,
            "CPU",
            config={"CPU_THREADS_NUM": "4"}
        )
        self.input_layer = self.compiled_model.input(0)
        self.output_layer = self.compiled_model.output(0)
        
        # Get input shape
        self.input_shape = self.input_layer.shape  # (1, 3, 640, 640)
        
    def preprocess(self, image_path):
        """Preprocess image for YOLO26"""
        img = cv2.imread(image_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_resized = cv2.resize(img, (640, 640))
        img_normalized = img_resized / 255.0  # Normalize to [0, 1]
        img_transposed = np.transpose(img_normalized, (2, 0, 1))  # HWC -> CHW
        img_batched = np.expand_dims(img_transposed, axis=0)  # Add batch dim
        return img_batched.astype(np.float32), img.shape
    
    def detect(self, image_path):
        """Run inference"""
        input_tensor, orig_shape = self.preprocess(image_path)
        
        # Inference
        results = self.compiled_model([input_tensor])[self.output_layer]
        
        # Post-process results
        detections = self.postprocess(results, orig_shape)
        return detections
    
    def postprocess(self, output, orig_shape):
        """
        YOLO26 NMS-free output: (1, 300, 6)
        Format: [x1, y1, x2, y2, confidence, class_id]
        """
        detections = output[0]  # Remove batch dimension
        
        # Filter by confidence
        mask = detections[:, 4] > 0.75
        filtered = detections[mask]
        
        # Scale boxes to original image size
        h, w = orig_shape[:2]
        scale_x, scale_y = w / 640, h / 640
        filtered[:, [0, 2]] *= scale_x
        filtered[:, [1, 3]] *= scale_y
        
        return filtered

# Usage
detector = OpenVINODetector("models/production/yolo26n_int8.xml")
detections = detector.detect("snapshot.jpg")
```

**Benefit**: Lower latency (no Python wrapper overhead), full control

---

## Integration with ML Detector Service

### Update `src/inference/detector_service.py`:
```python
import os
from ultralytics import YOLO
import logging

logger = logging.getLogger(__name__)

class DetectorService:
    """Persistent YOLO26 OpenVINO INT8 detector"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        logger.info(f"Loading YOLO26 OpenVINO INT8 model from {model_path}")
        
        # Load model
        self.model = YOLO(model_path)
        
        # Warm-up (critical for OpenVINO performance)
        logger.info("Warming up model...")
        dummy_image = "data/snapshots/dummy.jpg"  # Create 640x640 test image
        for _ in range(20):
            self.model.predict(dummy_image, verbose=False, device="intel:cpu")
        
        logger.info("Model loaded and warmed up")
    
    def detect_deer(self, image_path: str, confidence_threshold: float = 0.75):
        """
        Detect deer in image using YOLO26 OpenVINO INT8
        
        Returns:
            dict: {
                "deer_detected": bool,
                "confidence": float,
                "bounding_boxes": list of [x1, y1, x2, y2, conf]
            }
        """
        results = self.model.predict(
            image_path,
            conf=confidence_threshold,
            device="intel:cpu",
            verbose=False,
            classes=[0]  # Assuming class 0 is "deer"
        )
        
        result = results[0]
        boxes = result.boxes
        
        if len(boxes) == 0:
            return {
                "deer_detected": False,
                "confidence": 0.0,
                "bounding_boxes": []
            }
        
        # Get highest confidence detection
        confidences = boxes.conf.cpu().numpy()
        max_conf_idx = confidences.argmax()
        max_confidence = float(confidences[max_conf_idx])
        
        # Extract bounding boxes
        bboxes = []
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = float(box.conf[0])
            bboxes.append([float(x1), float(y1), float(x2), float(y2), conf])
        
        return {
            "deer_detected": True,
            "confidence": max_confidence,
            "bounding_boxes": bboxes
        }

# Initialize detector once at startup
DETECTOR = DetectorService("models/production/yolo26n_int8_openvino_model/")

# FastAPI endpoint
from fastapi import FastAPI
app = FastAPI()

@app.post("/detect")
async def detect(image_path: str):
    result = DETECTOR.detect_deer(image_path)
    return result
```

---

## Performance Monitoring

### Latency Tracking
```python
import time
import statistics

class PerformanceMonitor:
    def __init__(self):
        self.inference_times = []
    
    def log_inference_time(self, duration_ms):
        self.inference_times.append(duration_ms)
        if len(self.inference_times) > 1000:
            self.inference_times.pop(0)  # Keep last 1000
    
    def get_stats(self):
        if not self.inference_times:
            return {}
        return {
            "mean_ms": statistics.mean(self.inference_times),
            "median_ms": statistics.median(self.inference_times),
            "p95_ms": sorted(self.inference_times)[int(len(self.inference_times) * 0.95)],
            "p99_ms": sorted(self.inference_times)[int(len(self.inference_times) * 0.99)],
            "min_ms": min(self.inference_times),
            "max_ms": max(self.inference_times)
        }

monitor = PerformanceMonitor()

# In detect_deer method:
start = time.time()
results = self.model.predict(...)
duration_ms = (time.time() - start) * 1000
monitor.log_inference_time(duration_ms)
```

### Expose Metrics Endpoint
```python
@app.get("/metrics")
async def get_metrics():
    return {
        "model": "yolo26n_int8_openvino",
        "device": "intel:cpu (i7-4790)",
        "performance": monitor.get_stats()
    }
```

---

## Troubleshooting

### Issue 1: Slower than expected
**Symptoms**: INT8 inference >50ms

**Solutions**:
1. Ensure warm-up completed (20+ iterations)
2. Check CPU governor: `cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`
   - Should be "performance", not "powersave"
   - Set: `sudo cpupower frequency-set -g performance`
3. Disable hyperthreading if contention occurs
4. Verify OpenVINO using AVX2: Check logs for "AVX2" mention

### Issue 2: Accuracy degradation
**Symptoms**: INT8 mAP drop >2%

**Solutions**:
1. Increase calibration dataset size: `fraction=1.0` (use full dataset)
2. Ensure calibration data is representative (diverse lighting, angles, seasons)
3. Try mixed precision (keep sensitive layers in FP32):
   ```python
   # Advanced: Manually specify quantization config
   # See OpenVINO POT documentation
   ```

### Issue 3: False positives increased
**Symptoms**: More non-deer detections after INT8

**Solutions**:
1. Increase confidence threshold: `conf=0.80` (from 0.75)
2. Retrain with more negative examples
3. Use FP32 for final deployment if accuracy critical

---

## Expected Results Summary

### Performance Targets (i7-4790 CPU)
| Metric | Target | Expected |
|--------|--------|----------|
| Inference Time (INT8) | <40ms | 25-35ms |
| Total Latency | <50ms | 30-45ms |
| Accuracy Drop | <2% mAP | 0.5-1.5% |
| Model Size | <10MB | ~6MB |
| Memory Usage | <500MB | ~300MB |

### Speedup vs Current YOLOv8 PyTorch
- Current YOLOv8 PyTorch: ~150-200ms
- YOLO26 OpenVINO INT8: ~25-35ms
- **Speedup: 5-7x faster!**

---

## Next Steps

1. **Export YOLOv8 to OpenVINO INT8 (Baseline)**
   - Get current performance metrics
   - Establish accuracy baseline

2. **Train YOLO26 on Your Dataset**
   - Use existing annotated deer data
   - Target: Match/exceed YOLOv8 accuracy

3. **Export YOLO26 to OpenVINO INT8**
   - Benchmark speed on i7-4790
   - Validate <2% accuracy drop

4. **A/B Test in Production**
   - Run both models side-by-side
   - Compare false positive rates
   - Monitor latency over 1 week

5. **Full Deployment**
   - Switch coordinator to YOLO26 INT8
   - Update documentation
   - Archive YOLOv8 as backup

---

## References

- [OpenVINO INT8 Quantization Guide](https://docs.openvino.ai/2025/openvino-workflow/model-optimization-guide/quantizing-models-post-training.html)
- [YOLO26 OpenVINO Integration](https://docs.ultralytics.com/integrations/openvino/)
- [Ultralytics Export Documentation](https://docs.ultralytics.com/modes/export/)
- [OpenVINO CPU Optimization](https://docs.openvino.ai/2025/openvino-workflow/running-inference/inference-devices-and-modes/cpu-device.html)

---

## Cost Analysis

### Current System (YOLOv8 PyTorch)
- Inference: 150-200ms per snapshot
- Snapshot rate: 1 per minute (Side camera only)
- Daily inferences: 1,440
- Total daily compute: ~4 hours CPU time

### New System (YOLO26 OpenVINO INT8)
- Inference: 25-35ms per snapshot
- Snapshot rate: 1 per minute
- Daily inferences: 1,440
- Total daily compute: ~36 minutes CPU time

**CPU Time Savings**: 88% reduction (4 hours → 36 minutes)

**Benefits**:
- Lower server power consumption
- More CPU headroom for other tasks
- Faster response to motion events
- Could enable 30-second snapshot intervals if desired

---

## Conclusion

**YOLO26 + OpenVINO INT8 is the optimal solution for your i7-4790 CPU deployment.**

Key Advantages:
1. **5-7x speedup** (150ms → 25-35ms)
2. **Minimal accuracy loss** (<2% mAP drop)
3. **Smaller model** (~6MB vs ~30MB)
4. **Native Intel optimization** (AVX2, Haswell support)
5. **No hardware upgrade needed**

Your i7-4790 is actually a great CPU for this workload - Haswell's AVX2 support makes it competitive with much newer CPUs for INT8 inference.

Ready to proceed with implementation?
