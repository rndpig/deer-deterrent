"""
Deer detection inference engine for real-time detection.
"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from ultralytics import YOLO
import yaml


class DeerDetector:
    """Real-time deer detection using trained YOLO model."""
    
    def __init__(
        self,
        model_path: str = "models/production/best.pt",
        conf_threshold: float = 0.6,
        iou_threshold: float = 0.45
    ):
        """
        Initialize deer detector.
        
        Args:
            model_path: Path to trained YOLO model
            conf_threshold: Confidence threshold for detections
            iou_threshold: IOU threshold for NMS
        """
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Model not found: {self.model_path}\n"
                "Please train a model first: python src/training/train.py"
            )
        
        print(f"Loading deer detection model from {self.model_path}...")
        self.model = YOLO(str(self.model_path))
        print("✓ Model loaded successfully")
    
    def detect(
        self,
        image: np.ndarray,
        return_annotated: bool = False
    ) -> Tuple[List[dict], Optional[np.ndarray]]:
        """
        Detect deer in an image.
        
        Args:
            image: Input image as numpy array (BGR format)
            return_annotated: If True, return image with bounding boxes drawn
            
        Returns:
            Tuple of (detections list, annotated image)
            Each detection is a dict with: bbox, confidence, class_name
        """
        # Run inference
        results = self.model.predict(
            image,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            verbose=False
        )
        
        detections = []
        
        if len(results) > 0:
            result = results[0]
            
            # Extract detections
            if result.boxes is not None:
                boxes = result.boxes.xyxy.cpu().numpy()  # x1, y1, x2, y2
                confidences = result.boxes.conf.cpu().numpy()
                classes = result.boxes.cls.cpu().numpy()
                
                for box, conf, cls in zip(boxes, confidences, classes):
                    x1, y1, x2, y2 = box
                    
                    detections.append({
                        'bbox': {
                            'x1': float(x1),
                            'y1': float(y1),
                            'x2': float(x2),
                            'y2': float(y2),
                            'center_x': float((x1 + x2) / 2),
                            'center_y': float((y1 + y2) / 2)
                        },
                        'confidence': float(conf),
                        'class_id': int(cls),
                        'class_name': 'deer'
                    })
        
        # Generate annotated image if requested
        annotated_image = None
        if return_annotated and len(results) > 0:
            annotated_image = results[0].plot()
        
        return detections, annotated_image
    
    def detect_in_zones(
        self,
        image: np.ndarray,
        zones: List[dict]
    ) -> dict:
        """
        Detect deer and map them to specific zones.
        
        Args:
            image: Input image
            zones: List of zone definitions with detection_area
            
        Returns:
            Dictionary mapping zone names to deer detections in that zone
        """
        detections, _ = self.detect(image)
        
        img_height, img_width = image.shape[:2]
        zone_detections = {}
        
        for zone in zones:
            zone_name = zone['name']
            area = zone['detection_area']
            
            # Convert normalized coordinates to pixel coordinates
            x_min = int(area['x_min'] * img_width)
            y_min = int(area['y_min'] * img_height)
            x_max = int(area['x_max'] * img_width)
            y_max = int(area['y_max'] * img_height)
            
            # Find detections in this zone
            zone_deer = []
            for detection in detections:
                center_x = detection['bbox']['center_x']
                center_y = detection['bbox']['center_y']
                
                # Check if detection center is within zone
                if (x_min <= center_x <= x_max and 
                    y_min <= center_y <= y_max):
                    zone_deer.append(detection)
            
            if zone_deer:
                zone_detections[zone_name] = zone_deer
        
        return zone_detections
    
    def visualize_detection(
        self,
        image: np.ndarray,
        detections: List[dict],
        save_path: Optional[str] = None
    ) -> np.ndarray:
        """
        Draw bounding boxes on image.
        
        Args:
            image: Input image
            detections: List of detections from detect()
            save_path: Optional path to save annotated image
            
        Returns:
            Annotated image
        """
        annotated = image.copy()
        
        for det in detections:
            bbox = det['bbox']
            conf = det['confidence']
            
            # Draw bounding box
            x1, y1 = int(bbox['x1']), int(bbox['y1'])
            x2, y2 = int(bbox['x2']), int(bbox['y2'])
            
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw label
            label = f"Deer {conf:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(
                annotated,
                (x1, y1 - label_size[1] - 4),
                (x1 + label_size[0], y1),
                (0, 255, 0),
                -1
            )
            cv2.putText(
                annotated,
                label,
                (x1, y1 - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 0),
                2
            )
        
        if save_path:
            cv2.imwrite(save_path, annotated)
        
        return annotated


def main():
    """Test deer detection on sample images."""
    print("Deer Detection Inference Test")
    print("=" * 50)
    
    try:
        detector = DeerDetector()
        
        # Test on images in data/test if available
        test_dir = Path("data/processed/images/test")
        
        if not test_dir.exists():
            print(f"\n⚠ Test directory not found: {test_dir}")
            print("Please prepare your dataset first:")
            print("  python src/data/prepare_dataset.py")
            return
        
        test_images = list(test_dir.glob("*.jpg")) + list(test_dir.glob("*.png"))
        
        if not test_images:
            print(f"\n⚠ No test images found in {test_dir}")
            return
        
        print(f"\nFound {len(test_images)} test images")
        
        # Create output directory
        output_dir = Path("temp/detections")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Test on first 5 images
        for i, img_path in enumerate(test_images[:5], 1):
            print(f"\n[{i}/5] Processing {img_path.name}...")
            
            # Load image
            image = cv2.imread(str(img_path))
            
            # Detect
            detections, annotated = detector.detect(image, return_annotated=True)
            
            print(f"  Found {len(detections)} deer")
            for det in detections:
                print(f"    - Confidence: {det['confidence']:.3f}")
            
            # Save annotated image
            if annotated is not None:
                output_path = output_dir / f"detected_{img_path.name}"
                cv2.imwrite(str(output_path), annotated)
                print(f"  Saved to: {output_path}")
        
        print(f"\n✓ Test complete! Check results in {output_dir}")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        raise


if __name__ == "__main__":
    main()
