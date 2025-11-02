# Deer Deterrent System

An AI-powered deer detection and deterrent system that monitors Ring camera feeds and automatically activates sprinklers to deter deer from your property.

## Overview

This project uses machine learning to detect deer in real-time from Ring camera footage and automatically triggers Rainbird irrigation zones to humanely deter them from eating plants and causing damage.

## System Architecture

1. **Data Collection & Training**: Annotated images from Google Drive used to train a deer detection model
2. **Ring Camera Integration**: Real-time monitoring of camera feeds via Ring API
3. **Deer Detection**: ML model inference on camera frames to detect deer presence
4. **Rainbird Controller**: Automatic activation of specific irrigation zones when deer are detected

## Project Structure

```
deer-deterrent/
├── data/                    # Dataset storage
│   ├── raw/                # Raw annotated images from Google Drive
│   ├── processed/          # Processed datasets (train/val/test splits)
│   └── annotations/        # Annotation files
├── models/                  # Trained model storage
│   ├── checkpoints/        # Training checkpoints
│   └── production/         # Production-ready models
├── src/                     # Source code
│   ├── data/               # Data management utilities
│   ├── training/           # Model training scripts
│   ├── inference/          # Real-time inference engine
│   ├── integrations/       # Ring & Rainbird API integrations
│   └── utils/              # Shared utilities
├── configs/                 # Configuration files
├── notebooks/              # Jupyter notebooks for exploration
├── tests/                  # Unit and integration tests
├── logs/                   # Application logs
└── requirements.txt        # Python dependencies
```

## Prerequisites

- Python 3.9+
- Ring account with camera access
- Rainbird irrigation controller with API access
- Google Drive with annotated deer images
- GPU recommended for model training (CPU works but slower)

## Installation

1. Clone or navigate to this repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

1. Copy `.env.example` to `.env` and fill in your API credentials:
   - Ring API credentials
   - Rainbird controller credentials
   - Google Drive access (for data download)

2. Configure detection zones and sprinkler mappings in `configs/zones.yaml`

## Getting Started

### Step 1: Download Training Data
```bash
python src/data/download_from_gdrive.py
```

### Step 2: Train the Model
```bash
python src/training/train.py --config configs/training_config.yaml
```

### Step 3: Run the Deterrent System
```bash
python src/main.py
```

## Usage

- **Training Mode**: Train or fine-tune the deer detection model
- **Live Mode**: Monitor Ring cameras and activate sprinklers automatically
- **Test Mode**: Test detection on sample images without activating sprinklers

## Safety Features

- Configurable cooldown periods to prevent excessive sprinkler activation
- Time-based rules (e.g., only active at night)
- Confidence thresholds to reduce false positives
- Manual override capabilities

## Contributing

This is a personal project, but suggestions and improvements are welcome!

## License

MIT License

## Acknowledgments

Built to protect gardens from hungry deer while using humane deterrent methods.
