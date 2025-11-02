"""
Dataset preparation script for organizing and splitting annotated deer images.
"""
import os
import shutil
import yaml
from pathlib import Path
from typing import Tuple, List
import random
from collections import defaultdict


class DatasetPreparator:
    """Prepare dataset for training by organizing and splitting data."""
    
    def __init__(
        self,
        raw_dir: str = "data/raw",
        output_dir: str = "data/processed",
        config_path: str = "configs/training_config.yaml"
    ):
        self.raw_dir = Path(raw_dir)
        self.output_dir = Path(output_dir)
        
        # Load config
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self.train_split = config['data']['train_split']
        self.val_split = config['data']['val_split']
        self.test_split = config['data']['test_split']
        
        # Validate splits
        total = self.train_split + self.val_split + self.test_split
        assert abs(total - 1.0) < 0.01, f"Splits must sum to 1.0, got {total}"
    
    def prepare_yolo_dataset(self) -> None:
        """
        Organize dataset in YOLO format:
        data/processed/
          ├── images/
          │   ├── train/
          │   ├── val/
          │   └── test/
          ├── labels/
          │   ├── train/
          │   ├── val/
          │   └── test/
          └── dataset.yaml
        """
        print("Preparing YOLO dataset...")
        
        # Create directory structure
        splits = ['train', 'val', 'test']
        for split in splits:
            (self.output_dir / 'images' / split).mkdir(parents=True, exist_ok=True)
            (self.output_dir / 'labels' / split).mkdir(parents=True, exist_ok=True)
        
        # Find all image-annotation pairs
        pairs = self._find_image_annotation_pairs()
        print(f"Found {len(pairs)} image-annotation pairs")
        
        if len(pairs) == 0:
            raise ValueError(
                f"No image-annotation pairs found in {self.raw_dir}. "
                "Please check your data directory."
            )
        
        # Split dataset
        random.shuffle(pairs)
        train_count = int(len(pairs) * self.train_split)
        val_count = int(len(pairs) * self.val_split)
        
        train_pairs = pairs[:train_count]
        val_pairs = pairs[train_count:train_count + val_count]
        test_pairs = pairs[train_count + val_count:]
        
        # Copy files
        self._copy_pairs(train_pairs, 'train')
        self._copy_pairs(val_pairs, 'val')
        self._copy_pairs(test_pairs, 'test')
        
        # Create dataset.yaml
        self._create_dataset_yaml()
        
        print("\n✓ Dataset preparation complete!")
        print(f"  Train: {len(train_pairs)} images")
        print(f"  Val:   {len(val_pairs)} images")
        print(f"  Test:  {len(test_pairs)} images")
    
    def _find_image_annotation_pairs(self) -> List[Tuple[Path, Path]]:
        """Find all matching image and annotation file pairs."""
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        annotation_extensions = {'.txt'}
        
        # Group by stem (filename without extension)
        files_by_stem = defaultdict(lambda: {'image': None, 'annotation': None})
        
        for file_path in self.raw_dir.rglob('*'):
            if file_path.is_file():
                stem = file_path.stem
                if file_path.suffix.lower() in image_extensions:
                    files_by_stem[stem]['image'] = file_path
                elif file_path.suffix.lower() in annotation_extensions:
                    files_by_stem[stem]['annotation'] = file_path
        
        # Extract pairs where both image and annotation exist
        pairs = []
        for stem, files in files_by_stem.items():
            if files['image'] and files['annotation']:
                pairs.append((files['image'], files['annotation']))
            elif files['image']:
                print(f"Warning: Image without annotation: {files['image'].name}")
            elif files['annotation']:
                print(f"Warning: Annotation without image: {files['annotation'].name}")
        
        return pairs
    
    def _copy_pairs(self, pairs: List[Tuple[Path, Path]], split: str) -> None:
        """Copy image-annotation pairs to the appropriate split directory."""
        for img_path, ann_path in pairs:
            # Copy image
            img_dest = self.output_dir / 'images' / split / img_path.name
            shutil.copy2(img_path, img_dest)
            
            # Copy annotation
            ann_dest = self.output_dir / 'labels' / split / ann_path.name
            shutil.copy2(ann_path, ann_dest)
    
    def _create_dataset_yaml(self) -> None:
        """Create dataset.yaml file for YOLO training."""
        yaml_content = {
            'path': str(self.output_dir.absolute()),
            'train': 'images/train',
            'val': 'images/val',
            'test': 'images/test',
            'names': {
                0: 'deer'
            },
            'nc': 1  # number of classes
        }
        
        yaml_path = self.output_dir / 'dataset.yaml'
        with open(yaml_path, 'w') as f:
            yaml.dump(yaml_content, f, default_flow_style=False)
        
        print(f"\nCreated dataset config: {yaml_path}")


def main():
    """Main entry point for dataset preparation."""
    print("Deer Deterrent - Dataset Preparation")
    print("=" * 50)
    
    preparator = DatasetPreparator()
    
    try:
        preparator.prepare_yolo_dataset()
        print("\nNext step:")
        print("  Start training: python src/training/train.py")
    except Exception as e:
        print(f"\n✗ Error: {e}")


if __name__ == "__main__":
    main()
