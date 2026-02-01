"""
Visualize predictions vs ground truth to understand the mismatch.
Draw both on the same image to see spatial differences.
"""
from ultralytics import YOLO
import cv2
import os

# Load model and get first validation image
model = YOLO("models/production/best.pt")
val_dir = "data/training_datasets/v1.0_2026-01-baseline/images/val"
label_dir = "data/training_datasets/v1.0_2026-01-baseline/labels/val"

# Get first image
val_images = sorted([f for f in os.listdir(val_dir) if f.endswith('.jpg')])
first_image = val_images[0]
image_path = os.path.join(val_dir, first_image)
label_path = os.path.join(label_dir, first_image.replace('.jpg', '.txt'))

print(f"\n{'='*60}")
print(f"Analyzing: {first_image}")
print(f"{'='*60}\n")

# Load image
img = cv2.imread(image_path)
h, w = img.shape[:2]
print(f"Image size: {w}x{h}")

# Load ground truth
print(f"\n### Ground Truth Labels ###")
with open(label_path, 'r') as f:
    gt_lines = f.readlines()
    for i, line in enumerate(gt_lines):
        parts = line.strip().split()
        cls, x, y, bw, bh = map(float, parts)
        print(f"GT {i+1}: x={x:.6f}, y={y:.6f}, w={bw:.6f}, h={bh:.6f}")
        
        # Draw green box for ground truth
        x1 = int((x - bw/2) * w)
        y1 = int((y - bh/2) * h)
        x2 = int((x + bw/2) * w)
        y2 = int((y + bh/2) * h)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 3)  # Green
        cv2.putText(img, f"GT{i+1}", (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

# Get predictions
print(f"\n### Model Predictions ###")
results = model.predict(image_path, conf=0.25, verbose=False)
boxes = results[0].boxes

if len(boxes) > 0:
    for i, box in enumerate(boxes):
        conf = float(box.conf[0])
        # Get normalized coordinates
        x1n, y1n, x2n, y2n = box.xyxyn[0].cpu().numpy()
        x_center = (x1n + x2n) / 2
        y_center = (y1n + y2n) / 2
        box_w = x2n - x1n
        box_h = y2n - y1n
        
        print(f"Pred {i+1}: conf={conf:.4f}, x={x_center:.6f}, y={y_center:.6f}, w={box_w:.6f}, h={box_h:.6f}")
        
        # Draw red box for predictions
        x1 = int(x1n * w)
        y1 = int(y1n * h)
        x2 = int(x2n * w)
        y2 = int(y2n * h)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)  # Red
        cv2.putText(img, f"P{i+1}:{conf:.2f}", (x1, y2+15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
else:
    print("No predictions found!")

# Save visualization
output_path = "data/training_datasets/v1.0_2026-01-baseline/bbox_comparison.jpg"
cv2.imwrite(output_path, img)
print(f"\n{'='*60}")
print(f"Visualization saved to: {output_path}")
print(f"Green boxes = Ground Truth")
print(f"Red boxes = Model Predictions (conf >= 0.25)")
print(f"{'='*60}\n")
