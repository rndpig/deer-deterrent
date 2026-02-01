"""
Review pseudo-labels generated from YOLOv8n predictions.
Visualize random samples to verify quality before training YOLO26.
"""
import cv2
import os
import random
from pathlib import Path

V1_1_DATASET = "data/training_datasets/v1.1_2026-01-pseudolabels"
OUTPUT_DIR = "data/training_datasets/v1.1_2026-01-pseudolabels/review_samples"

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("\n" + "="*70)
print("Pseudo-Label Quality Review")
print("="*70)

for split in ['train', 'val']:
    print(f"\n### Reviewing {split.upper()} split ###")
    
    image_dir = f"{V1_1_DATASET}/images/{split}"
    label_dir = f"{V1_1_DATASET}/labels/{split}"
    
    # Get images with labels (positive examples)
    images_with_labels = []
    for label_file in os.listdir(label_dir):
        if label_file.endswith('.txt'):
            img_name = label_file.replace('.txt', '.jpg')
            img_path = os.path.join(image_dir, img_name)
            if os.path.exists(img_path):
                images_with_labels.append(img_name)
    
    # Get images without labels (negatives)
    all_images = [f for f in os.listdir(image_dir) if f.endswith('.jpg')]
    images_without_labels = [img for img in all_images if img not in images_with_labels]
    
    print(f"  Images with labels (positives): {len(images_with_labels)}")
    print(f"  Images without labels (negatives): {len(images_without_labels)}")
    
    # Sample 3 positive examples
    if images_with_labels:
        samples = random.sample(images_with_labels, min(3, len(images_with_labels)))
        
        for img_name in samples:
            img_path = os.path.join(image_dir, img_name)
            label_path = os.path.join(label_dir, img_name.replace('.jpg', '.txt'))
            
            img = cv2.imread(img_path)
            h, w = img.shape[:2]
            
            # Draw bboxes
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    cls, x, y, bw, bh = map(float, parts)
                    
                    # Convert YOLO format to pixel coords
                    x1 = int((x - bw/2) * w)
                    y1 = int((y - bh/2) * h)
                    x2 = int((x + bw/2) * w)
                    y2 = int((y + bh/2) * h)
                    
                    # Draw green bbox (pseudo-label from YOLOv8n)
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(img, "YOLOv8n", (x1, y1-5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Save review image
            output_path = os.path.join(OUTPUT_DIR, f"{split}_{img_name}")
            cv2.imwrite(output_path, img)
            print(f"    Saved: {output_path}")
    
    # Sample 2 negative examples
    if images_without_labels:
        neg_samples = random.sample(images_without_labels, min(2, len(images_without_labels)))
        
        for img_name in neg_samples:
            img_path = os.path.join(image_dir, img_name)
            img = cv2.imread(img_path)
            
            # Add text indicating negative example
            cv2.putText(img, "NEGATIVE (no deer)", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            output_path = os.path.join(OUTPUT_DIR, f"{split}_negative_{img_name}")
            cv2.imwrite(output_path, img)
            print(f"    Saved: {output_path}")

print(f"\n{'='*70}")
print(f"Review complete! Check images in:")
print(f"  {OUTPUT_DIR}/")
print(f"\nGreen boxes = YOLOv8n pseudo-labels (conf >= 0.75)")
print(f"Red text = Negative examples (no deer)")
print(f"\nIf labels look good, proceed with YOLO26 training!")
print(f"{'='*70}\n")
