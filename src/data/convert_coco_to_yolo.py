"""
Convert COCO format annotations to YOLO format for training.
"""
import json
import shutil
from pathlib import Path
from typing import Dict, List


class COCOtoYOLOConverter:
    """Convert COCO annotations to YOLO format."""
    
    def __init__(
        self,
        coco_json_path: str = "data/raw/videos/annotations/result.json",
        images_dir: str = "data/raw/videos/annotations/images",
        output_dir: str = "data/raw"
    ):
        self.coco_json_path = Path(coco_json_path)
        self.images_dir = Path(images_dir)
        self.output_dir = Path(output_dir)
        
        # Load COCO annotations
        with open(self.coco_json_path, 'r') as f:
            self.coco_data = json.load(f)
        
        # Create output directories
        self.images_output = self.output_dir / "images"
        self.labels_output = self.output_dir / "labels"
        self.images_output.mkdir(parents=True, exist_ok=True)
        self.labels_output.mkdir(parents=True, exist_ok=True)
    
    def convert(self) -> None:
        """Convert COCO to YOLO format."""
        print("Converting COCO annotations to YOLO format...")
        print(f"Input: {self.coco_json_path}")
        print(f"Output: {self.output_dir}")
        
        # Build image ID to filename mapping
        image_id_to_info = {
            img['id']: img for img in self.coco_data['images']
        }
        
        # Build image ID to annotations mapping
        image_id_to_annots = {}
        for annot in self.coco_data['annotations']:
            image_id = annot['image_id']
            if image_id not in image_id_to_annots:
                image_id_to_annots[image_id] = []
            image_id_to_annots[image_id].append(annot)
        
        # Process each image
        processed = 0
        skipped = 0
        
        for image_id, image_info in image_id_to_info.items():
            # Get image file
            image_filename = image_info['file_name']
            # Strip the "images\1\" or "images/1/" prefix if present
            image_filename = Path(image_filename).name
            image_path = self.images_dir / image_filename
            
            if not image_path.exists():
                print(f"Warning: Image not found: {image_path}")
                skipped += 1
                continue
            
            # Get image dimensions
            width = image_info['width']
            height = image_info['height']
            
            # Get annotations for this image
            annotations = image_id_to_annots.get(image_id, [])
            
            if not annotations:
                print(f"Warning: No annotations for: {image_filename}")
                skipped += 1
                continue
            
            # Convert annotations to YOLO format
            yolo_annotations = []
            for annot in annotations:
                # COCO bbox format: [x, y, width, height]
                bbox = annot['bbox']
                x, y, w, h = bbox
                
                # Convert to YOLO format: [class, x_center, y_center, width, height]
                # All values normalized to 0-1
                x_center = (x + w / 2) / width
                y_center = (y + h / 2) / height
                norm_width = w / width
                norm_height = h / height
                
                # Class ID (0 for deer, since we only have one class)
                class_id = 0
                
                yolo_annotations.append(
                    f"{class_id} {x_center:.6f} {y_center:.6f} {norm_width:.6f} {norm_height:.6f}"
                )
            
            # Save image (copy to output)
            output_image_path = self.images_output / image_filename
            shutil.copy2(image_path, output_image_path)
            
            # Save YOLO label file
            label_filename = Path(image_filename).stem + ".txt"
            label_path = self.labels_output / label_filename
            
            with open(label_path, 'w') as f:
                f.write('\n'.join(yolo_annotations))
            
            processed += 1
        
        print(f"\n✓ Conversion complete!")
        print(f"  Processed: {processed} images")
        print(f"  Skipped: {skipped} images")
        print(f"  Images saved to: {self.images_output}")
        print(f"  Labels saved to: {self.labels_output}")


def main():
    """Main entry point."""
    print("COCO to YOLO Conversion")
    print("=" * 50)
    
    converter = COCOtoYOLOConverter()
    
    try:
        converter.convert()
        print("\nNext step:")
        print("  Run: python src/data/prepare_dataset.py")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    main()
