"""
Deer detection inference engine using OpenVINO for optimized CPU inference.
Provides 1.94x speedup over PyTorch on Intel CPUs.
"""
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class DeerDetectorOpenVINO:
    """Real-time deer detection using OpenVINO-optimized YOLO model."""
    
    def __init__(
        self,
        model_path: str = "models/production/best_openvino_model",
        conf_threshold: float = 0.6,
        iou_threshold: float = 0.45
    ):
        """
        Initialize OpenVINO deer detector.
        
        Args:
            model_path: Path to OpenVINO model directory or .xml file
            conf_threshold: Confidence threshold for detections
            iou_threshold: IOU threshold for NMS
        """
        try:
            import openvino as ov
        except ImportError:
            raise ImportError(
                "OpenVINO not installed. Install with: pip install openvino"
            )
        
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        
        # Handle both directory and .xml file paths
        model_path = Path(model_path)
        if model_path.is_dir():
            # Look for .xml file in directory
            xml_files = list(model_path.glob("*.xml"))
            if not xml_files:
                raise FileNotFoundError(f"No .xml model found in {model_path}")
            model_path = xml_files[0]
        
        if not model_path.exists():
            raise FileNotFoundError(
                f"Model not found: {model_path}\n"
                "Please export model first: python export_to_openvino.py"
            )
        
        logger.info(f"Loading OpenVINO model from {model_path}...")
        
        # Initialize OpenVINO
        self.core = ov.Core()
        self.model = self.core.read_model(model_path)
        self.compiled_model = self.core.compile_model(self.model, "CPU")
        
        # Get input/output layers
        self.input_layer = self.compiled_model.input(0)
        self.output_layer = self.compiled_model.output(0)
        
        # Get input shape (should be [1, 3, 640, 640])
        self.input_shape = self.input_layer.shape
        self.input_height = self.input_shape[2]
        self.input_width = self.input_shape[3]
        
        logger.info(f"✓ OpenVINO model loaded (input: {self.input_shape})")
        logger.info(f"  Confidence threshold: {self.conf_threshold}")
        logger.info(f"  IOU threshold: {self.iou_threshold}")
    
    def preprocess(self, image: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int]]:
        """
        Preprocess image for YOLO inference using simple resize (no letterbox).
        This matches the default OpenVINO export behavior.
        
        Args:
            image: Input image (BGR format)
            
        Returns:
            Tuple of (preprocessed image tensor [1, 3, 640, 640], original shape (h, w))
        """
        # Store original dimensions for scaling back
        orig_h, orig_w = image.shape[:2]
        
        # Convert BGR to RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Simple resize to 640x640 (no letterbox, no aspect ratio preservation)
        # This matches how OpenVINO models are typically exported
        image_resized = cv2.resize(image_rgb, (self.input_width, self.input_height), 
                                   interpolation=cv2.INTER_LINEAR)
        
        # Transpose to CHW format
        image_transposed = image_resized.transpose(2, 0, 1)
        
        # Normalize to [0, 1]
        image_normalized = image_transposed.astype(np.float32) / 255.0
        
        # Add batch dimension
        # Return original shape instead of padding
        return np.expand_dims(image_normalized, axis=0), (orig_h, orig_w)
    
    def postprocess(
        self,
        outputs: np.ndarray,
        orig_shape: Tuple[int, int],
        orig_dims: Tuple[int, int]
    ) -> List[dict]:
        """
        Post-process YOLO outputs to extract detections.
        Scales coordinates from 640x640 back to original image size.
        
        Args:
            outputs: Raw model outputs [1, 300, 6] where 6 = [x1, y1, x2, y2, conf, class]
            orig_shape: Original image shape (height, width) - same as orig_dims
            orig_dims: Original image dimensions (height, width) from preprocessing
            
        Returns:
            List of detections with confidence >= threshold
        """
        detections = []
        
        # outputs shape: [1, 300, 6]
        # Each detection: [x1, y1, x2, y2, confidence, class_id] in 640x640 space
        predictions = outputs[0]  # Remove batch dimension
        
        # Filter by confidence
        high_conf_mask = predictions[:, 4] >= self.conf_threshold
        filtered_predictions = predictions[high_conf_mask]
        
        if len(filtered_predictions) == 0:
            return detections
        
        # Extract boxes and confidences
        boxes_xyxy = filtered_predictions[:, :4]  # Coordinates in 640x640 space
        confidences = filtered_predictions[:, 4]
        
        # Apply NMS using OpenCV
        indices = cv2.dnn.NMSBoxes(
            boxes_xyxy.tolist(),
            confidences.tolist(),
            self.conf_threshold,
            self.iou_threshold
        )
        
        if len(indices) == 0:
            return detections
        
        # Scale boxes directly from 640x640 to original image size
        orig_h, orig_w = orig_dims
        scale_x = orig_w / self.input_width
        scale_y = orig_h / self.input_height
        
        for idx in indices.flatten():
            box = boxes_xyxy[idx]
            conf = confidences[idx]
            
            # Scale coordinates from 640x640 to original dimensions
            x1 = float(box[0] * scale_x)
            y1 = float(box[1] * scale_y)
            x2 = float(box[2] * scale_x)
            y2 = float(box[3] * scale_y)
            
            # Clip to image bounds
            x1 = max(0, min(x1, orig_w))
            y1 = max(0, min(y1, orig_h))
            x2 = max(0, min(x2, orig_w))
            y2 = max(0, min(y2, orig_h))
            
            detections.append({
                'bbox': {
                    'x1': x1,
                    'y1': y1,
                    'x2': x2,
                    'y2': y2,
                    'center_x': (x1 + x2) / 2,
                    'center_y': (y1 + y2) / 2
                },
                'confidence': float(conf),
                'class_id': 0,  # Only deer class
                'class_name': 'deer'
            })
        
        return detections
    
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
        # Store original shape
        orig_shape = image.shape[:2]
        
        # Preprocess (returns tensor and original dimensions)
        input_tensor, orig_dims = self.preprocess(image)
        
        # Run inference
        outputs = self.compiled_model([input_tensor])[self.output_layer]
        
        # Post-process (scale from 640x640 to original size)
        detections = self.postprocess(outputs, orig_shape, orig_dims)
        
        # Generate annotated image if requested
        annotated_image = None
        if return_annotated:
            annotated_image = image.copy()
            for det in detections:
                bbox = det['bbox']
                conf = det['confidence']
                
                # Draw bounding box
                cv2.rectangle(
                    annotated_image,
                    (int(bbox['x1']), int(bbox['y1'])),
                    (int(bbox['x2']), int(bbox['y2'])),
                    (0, 255, 0),
                    2
                )
                
                # Draw label
                label = f"deer {conf:.2f}"
                cv2.putText(
                    annotated_image,
                    label,
                    (int(bbox['x1']), int(bbox['y1']) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2
                )
        
        return detections, annotated_image
    
    def detect_from_file(
        self,
        image_path: str,
        return_annotated: bool = False
    ) -> Tuple[List[dict], Optional[np.ndarray]]:
        """
        Detect deer in an image file.
        
        Args:
            image_path: Path to image file
            return_annotated: If True, return image with bounding boxes drawn
            
        Returns:
            Tuple of (detections list, annotated image)
        """
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"Failed to load image: {image_path}")
        
        return self.detect(image, return_annotated)
