"""
Demo/Test mode for deer deterrent system using static images.
This allows testing the full detection pipeline without needing live camera feeds
or working irrigation controllers.
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime
import cv2

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.inference.detector import DeerDetector
from dotenv import load_dotenv

load_dotenv()


class MockDeerDeterrentSystem:
    """Demo system using static images for testing."""
    
    def __init__(self):
        """Initialize demo system."""
        print("=" * 60)
        print("Deer Deterrent System - DEMO MODE")
        print("=" * 60)
        print("\nUsing static images for testing")
        print("No actual cameras or irrigation will be used\n")
        
        # Initialize detector
        model_path = os.getenv("MODEL_PATH", "models/production/best.pt")
        conf_threshold = float(os.getenv("CONFIDENCE_THRESHOLD", 0.6))
        
        print("Loading deer detection model...")
        self.detector = DeerDetector(
            model_path=model_path,
            conf_threshold=conf_threshold
        )
        
        # Test images directory
        self.test_images_dir = Path("data/processed/images/test")
        
        if not self.test_images_dir.exists():
            print(f"\n⚠ Test images not found at {self.test_images_dir}")
            print("Please run: python src/data/prepare_dataset.py")
            return
        
        self.test_images = list(self.test_images_dir.glob("*.jpg"))
        print(f"\n✓ Found {len(self.test_images)} test images")
        
        # Output directory for annotated images
        self.output_dir = Path("temp/demo_detections")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"✓ Output directory: {self.output_dir}")
        print("=" * 60)
    
    def process_image(self, image_path: Path) -> None:
        """
        Process a single image through the detection pipeline.
        
        Args:
            image_path: Path to image file
        """
        print(f"\n{'='*60}")
        print(f"Processing: {image_path.name}")
        print(f"{'='*60}")
        
        # Load image
        image = cv2.imread(str(image_path))
        if image is None:
            print(f"✗ Failed to load image")
            return
        
        h, w = image.shape[:2]
        print(f"Image size: {w}x{h}")
        
        # Detect deer
        print("\nRunning detection...")
        detections, annotated = self.detector.detect(image, return_annotated=True)
        
        # Report results
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if detections:
            print(f"\n🦌 [{timestamp}] DEER DETECTED!")
            print(f"   Count: {len(detections)}")
            
            for i, det in enumerate(detections, 1):
                bbox = det['bbox']
                conf = det['confidence']
                
                print(f"\n   Deer #{i}:")
                print(f"     Confidence: {conf:.2%}")
                print(f"     Location: ({int(bbox['center_x'])}, {int(bbox['center_y'])})")
                print(f"     Size: {int(bbox['x2']-bbox['x1'])}x{int(bbox['y2']-bbox['y1'])} px")
            
            # Simulate zone mapping
            print(f"\n   💦 [DEMO] Would activate irrigation:")
            print(f"      Zone: Garage North (Zone #2)")
            print(f"      Duration: 30 seconds")
            print(f"      Cooldown: 5 minutes")
            
        else:
            print(f"\n✓ [{timestamp}] No deer detected")
        
        # Save annotated image
        if annotated is not None:
            output_path = self.output_dir / f"demo_{image_path.name}"
            cv2.imwrite(str(output_path), annotated)
            print(f"\n✓ Saved annotated image: {output_path}")
    
    def run_demo(self, num_images: int = 5, delay: float = 2.0) -> None:
        """
        Run demo processing on multiple images.
        
        Args:
            num_images: Number of images to process
            delay: Delay between images in seconds
        """
        if not self.test_images:
            print("\n⚠ No test images available")
            return
        
        print(f"\n{'='*60}")
        print(f"Starting demo with {min(num_images, len(self.test_images))} images")
        print(f"Delay between images: {delay}s")
        print(f"{'='*60}")
        
        for i, img_path in enumerate(self.test_images[:num_images], 1):
            print(f"\n[Image {i}/{min(num_images, len(self.test_images))}]")
            
            self.process_image(img_path)
            
            if i < min(num_images, len(self.test_images)):
                print(f"\n⏳ Waiting {delay}s before next image...")
                time.sleep(delay)
        
        print(f"\n{'='*60}")
        print(f"Demo complete!")
        print(f"{'='*60}")
        print(f"\nCheck annotated images in: {self.output_dir}")
        print(f"\nNext steps:")
        print(f"  1. Review detection accuracy")
        print(f"  2. Configure Ring camera integration (once library is fixed)")
        print(f"  3. Set up Rain Bird API (need to capture from mobile app)")
        print(f"  4. Deploy to QNAP NAS")
        print(f"  5. Build React dashboard")
    
    def interactive_mode(self) -> None:
        """Interactive mode for testing individual images."""
        if not self.test_images:
            print("\n⚠ No test images available")
            return
        
        print(f"\n{'='*60}")
        print("Interactive Demo Mode")
        print(f"{'='*60}")
        print("\nAvailable images:")
        
        for i, img_path in enumerate(self.test_images, 1):
            print(f"  {i}. {img_path.name}")
        
        print(f"\nCommands:")
        print(f"  1-{len(self.test_images)}: Process specific image")
        print(f"  'all': Process all images")
        print(f"  'quit' or 'q': Exit")
        
        while True:
            try:
                choice = input("\n> ").strip().lower()
                
                if choice in ['quit', 'q', 'exit']:
                    print("Exiting demo mode")
                    break
                
                elif choice == 'all':
                    self.run_demo(len(self.test_images))
                    break
                
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(self.test_images):
                        self.process_image(self.test_images[idx])
                    else:
                        print(f"Invalid index. Choose 1-{len(self.test_images)}")
                
                else:
                    print("Invalid command")
            
            except KeyboardInterrupt:
                print("\n\nExiting demo mode")
                break
            except Exception as e:
                print(f"Error: {e}")


def main():
    """Run demo system."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deer Deterrent Demo Mode")
    parser.add_argument(
        '--mode',
        choices=['auto', 'interactive'],
        default='auto',
        help='Run mode (default: auto)'
    )
    parser.add_argument(
        '--images',
        type=int,
        default=5,
        help='Number of images to process in auto mode (default: 5)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=2.0,
        help='Delay between images in seconds (default: 2.0)'
    )
    
    args = parser.parse_args()
    
    try:
        system = MockDeerDeterrentSystem()
        
        if args.mode == 'auto':
            system.run_demo(num_images=args.images, delay=args.delay)
        else:
            system.interactive_mode()
    
    except Exception as e:
        print(f"\n✗ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
