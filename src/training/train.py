"""
YOLO-based deer detection model training script.
"""
import os
import yaml
from pathlib import Path
from datetime import datetime
from ultralytics import YOLO
from dotenv import load_dotenv

load_dotenv()


class DeerDetectorTrainer:
    """Train a YOLO model for deer detection."""
    
    def __init__(self, config_path: str = "configs/training_config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.data_config = self.config['data']
        self.model_config = self.config['model']
        self.train_config = self.config['training']
        self.output_config = self.config['output']
        
        # Create output directory
        self.output_dir = Path(self.output_config['save_dir'])
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def train(self) -> None:
        """Train the deer detection model."""
        print("=" * 60)
        print("Deer Detection Model Training")
        print("=" * 60)
        
        # Initialize model
        model_name = self.model_config['architecture']
        print(f"\nInitializing {model_name} model...")
        
        if self.model_config['pretrained']:
            model = YOLO(f"{model_name}.pt")
            print(f"✓ Loaded pretrained {model_name} weights")
        else:
            model = YOLO(f"{model_name}.yaml")
            print(f"✓ Initialized {model_name} from scratch")
        
        # Dataset path
        dataset_yaml = Path(self.data_config['processed_dir']) / 'dataset.yaml'
        
        if not dataset_yaml.exists():
            raise FileNotFoundError(
                f"Dataset configuration not found: {dataset_yaml}\n"
                "Please run: python src/data/prepare_dataset.py"
            )
        
        print(f"\nDataset: {dataset_yaml}")
        print(f"Image size: {self.data_config['image_size']}")
        print(f"Epochs: {self.train_config['epochs']}")
        print(f"Batch size: {self.train_config['batch_size']}")
        print(f"Device: {self.train_config['device']}")
        
        # Training arguments
        train_args = {
            'data': str(dataset_yaml),
            'epochs': self.train_config['epochs'],
            'batch': self.train_config['batch_size'],
            'imgsz': self.data_config['image_size'],
            'device': self.train_config['device'],
            'workers': self.train_config['workers'],
            'optimizer': self.train_config['optimizer'],
            'lr0': self.train_config['learning_rate'],
            'momentum': self.train_config['momentum'],
            'weight_decay': self.train_config['weight_decay'],
            'warmup_epochs': self.train_config['warmup_epochs'],
            'patience': self.train_config['patience'],
            'save_period': self.output_config['save_period'],
            'project': str(self.output_dir),
            'name': f"{self.output_config['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'exist_ok': True,
            'pretrained': self.model_config['pretrained'],
            'verbose': True,
        }
        
        # Add augmentation parameters
        aug_config = self.config.get('augmentation', {})
        train_args.update({
            'hsv_h': aug_config.get('hsv_h', 0.015),
            'hsv_s': aug_config.get('hsv_s', 0.7),
            'hsv_v': aug_config.get('hsv_v', 0.4),
            'degrees': aug_config.get('degrees', 0.0),
            'translate': aug_config.get('translate', 0.1),
            'scale': aug_config.get('scale', 0.5),
            'shear': aug_config.get('shear', 0.0),
            'perspective': aug_config.get('perspective', 0.0),
            'flipud': aug_config.get('flipud', 0.0),
            'fliplr': aug_config.get('fliplr', 0.5),
            'mosaic': aug_config.get('mosaic', 1.0),
            'mixup': aug_config.get('mixup', 0.0),
        })
        
        print("\n" + "=" * 60)
        print("Starting training...")
        print("=" * 60 + "\n")
        
        # Train the model
        results = model.train(**train_args)
        
        print("\n" + "=" * 60)
        print("Training Complete!")
        print("=" * 60)
        
        # Save best model to production directory
        self._save_production_model(model, train_args['name'])
        
        # Print results
        self._print_results(results, train_args['name'])
    
    def _save_production_model(self, model, experiment_name: str) -> None:
        """Save the best model to production directory."""
        production_dir = Path("models/production")
        production_dir.mkdir(parents=True, exist_ok=True)
        
        # The best model is saved by YOLO in the experiment directory
        best_model_path = self.output_dir / experiment_name / "weights" / "best.pt"
        
        if best_model_path.exists():
            production_path = production_dir / "best.pt"
            import shutil
            shutil.copy2(best_model_path, production_path)
            print(f"\n✓ Production model saved: {production_path}")
        else:
            print(f"\n⚠ Warning: Best model not found at {best_model_path}")
    
    def _print_results(self, results, experiment_name: str) -> None:
        """Print training results summary."""
        results_dir = self.output_dir / experiment_name
        
        print(f"\nResults saved to: {results_dir}")
        print("\nFiles generated:")
        print(f"  - weights/best.pt (best model)")
        print(f"  - weights/last.pt (last checkpoint)")
        print(f"  - results.png (training metrics)")
        print(f"  - confusion_matrix.png")
        print(f"  - results.csv (detailed metrics)")
        
        print("\nNext steps:")
        print("  1. Review training metrics in results.png")
        print("  2. Test the model: python src/inference/test_model.py")
        print("  3. Run live detection: python src/main.py")


def main():
    """Main entry point for training."""
    trainer = DeerDetectorTrainer()
    
    try:
        trainer.train()
    except Exception as e:
        print(f"\n✗ Training failed: {e}")
        raise


if __name__ == "__main__":
    main()
