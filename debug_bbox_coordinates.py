"""
Debug script to check OpenVINO model output coordinate format.
"""
import cv2
import numpy as np
from pathlib import Path
from src.inference.detector_openvino import DeerDetectorOpenVINO

# Load a snapshot with known deer location
snapshot_path = "data/snapshots/ring_omotion_1737057802.jpg"  # Jan 16 snapshot with 4 deer

if not Path(snapshot_path).exists():
    print(f"Snapshot not found: {snapshot_path}")
    print("Please provide a valid snapshot path")
    exit(1)

# Load image
img = cv2.imread(snapshot_path)
print(f"Image shape: {img.shape}")  # Should be (height, width, 3)
h, w = img.shape[:2]
print(f"Image dimensions: {w}x{h}")

# Initialize detector
detector = DeerDetectorOpenVINO(
    model_path="models/production/openvino/best_fp16.xml",
    conf_threshold=0.15  # Low threshold to catch all deer
)

# Get raw model outputs (before postprocessing)
input_tensor, padding = detector.preprocess(img)
print(f"\nPreprocessing:")
print(f"  Input tensor shape: {input_tensor.shape}")
print(f"  Padding (top, left): {padding}")

# Run inference
outputs = detector.compiled_model([input_tensor])[detector.output_layer]
print(f"\nRaw model output:")
print(f"  Output shape: {outputs.shape}")
print(f"  Output dtype: {outputs.dtype}")

# Show first few predictions (high confidence)
predictions = outputs[0]  # Remove batch dimension
high_conf_mask = predictions[:, 4] >= 0.15
high_conf_preds = predictions[high_conf_mask]

print(f"\nHigh confidence predictions (>= 0.15): {len(high_conf_preds)}")
for i, pred in enumerate(high_conf_preds[:10]):  # Show first 10
    x1, y1, x2, y2, conf, cls = pred
    print(f"  Pred {i+1}: x1={x1:.2f}, y1={y1:.2f}, x2={x2:.2f}, y2={y2:.2f}, conf={conf:.4f}, cls={cls:.0f}")
    
    # Check if coordinates look normalized (0-1) or pixel-space (>1)
    if x2 <= 1.0 and y2 <= 1.0:
        print(f"    -> Coordinates appear NORMALIZED (0-1)")
    else:
        print(f"    -> Coordinates appear to be in PIXEL space")
    
    # Check if they're in 640x640 input space
    if x2 <= 640 and y2 <= 640:
        print(f"    -> Could be 640x640 input space")

# Now run full detection pipeline
print(f"\n{'='*70}")
print("Full detection pipeline:")
detections, annotated = detector.detect(img, return_annotated=True)

print(f"\nDetections after postprocessing: {len(detections)}")
for i, det in enumerate(detections):
    bbox = det['bbox']
    conf = det['confidence']
    print(f"  Detection {i+1}:")
    print(f"    x1={bbox['x1']:.2f}, y1={bbox['y1']:.2f}")
    print(f"    x2={bbox['x2']:.2f}, y2={bbox['y2']:.2f}")
    print(f"    confidence={conf:.4f}")
    print(f"    center_x={bbox['center_x']:.2f}, center_y={bbox['center_y']:.2f}")
    
    # Verify coordinates are within image bounds
    if bbox['x1'] < 0 or bbox['y1'] < 0 or bbox['x2'] > w or bbox['y2'] > h:
        print(f"    ⚠️ WARNING: Coordinates out of image bounds!")
    else:
        print(f"    ✓ Coordinates within bounds")

# Save annotated image
output_path = "debug_bbox_output.jpg"
cv2.imwrite(output_path, annotated)
print(f"\n✓ Annotated image saved to: {output_path}")
print(f"Review the image to see if bounding boxes are correctly positioned.")
