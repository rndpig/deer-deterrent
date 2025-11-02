# Getting Started with Your Deer Deterrent Project

This guide will walk you through the complete process from downloading your annotated images to running the live detection system.

## Phase 1: Setup & Data Preparation

### Step 1: Set Up Your Environment

1. **Create and activate a virtual environment:**
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. **Install dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Configure your credentials:**
   - Copy `.env.example` to `.env`
   - Edit `.env` and fill in your credentials:
     - Google Drive folder ID (where your annotated images are stored)
     - Ring camera username and password
     - Rainbird controller IP address and password

### Step 2: Download Your Annotated Dataset

Your annotated images are stored on Google Drive. To download them:

1. **Get your Google Drive folder ID:**
   - Open your Google Drive folder in a browser
   - The URL will look like: `https://drive.google.com/drive/folders/1ABC123XYZ...`
   - Copy the ID part (everything after `folders/`)
   - Add it to your `.env` file as `GOOGLE_DRIVE_FOLDER_ID`

2. **Make sure your folder is shared:**
   - Right-click the folder in Google Drive
   - Click "Share" → "Get link"
   - Set to "Anyone with the link can view"

3. **Download the data:**
   ```powershell
   python src/data/download_from_gdrive.py
   ```

This will download all your images and annotations to `data/raw/`.

### Step 3: Prepare the Dataset

Organize your data into training, validation, and test splits:

```powershell
python src/data/prepare_dataset.py
```

This creates a YOLO-format dataset in `data/processed/` with:
- 70% training data
- 20% validation data
- 10% test data

**Verify your data:**
- Check `data/processed/images/train/` for training images
- Check `data/processed/labels/train/` for corresponding annotations
- Review `data/processed/dataset.yaml` for the configuration

## Phase 2: Model Training

### Step 4: Train Your Deer Detection Model

Now train the YOLOv8 model on your annotated deer images:

```powershell
python src/training/train.py
```

**What to expect:**
- Training will take several hours depending on your hardware
- Progress will be shown in the terminal
- Results saved to `models/checkpoints/`
- Best model automatically copied to `models/production/best.pt`

**Monitor training:**
- Watch the loss values decrease over time
- Check `models/checkpoints/deer_detector_*/results.png` for metrics
- Review `models/checkpoints/deer_detector_*/confusion_matrix.png`

**GPU vs CPU:**
- GPU: ~30-60 minutes (recommended)
- CPU: 2-4 hours

### Step 5: Test Your Model

After training completes, test the model on sample images:

```powershell
python src/inference/detector.py
```

This will:
- Process images from your test set
- Show detection results in the console
- Save annotated images to `temp/detections/`

**Review the results:**
- Open images in `temp/detections/` to see bounding boxes
- Verify the model is detecting deer correctly
- If accuracy is low, you may need to train longer or add more data

## Phase 3: Integration Setup

### Step 6: Test Ring Camera Connection

```powershell
python src/integrations/ring_camera.py
```

**Troubleshooting:**
- If 2FA is enabled on your Ring account, you may need additional setup
- The script will list all your Ring cameras
- Verify your cameras appear in the list

### Step 7: Test Rainbird Controller

```powershell
python src/integrations/rainbird_controller.py
```

**Important Notes:**
- This does NOT activate sprinklers in test mode
- Verifies connection to your controller
- The Rainbird API varies by model - you may need to adjust endpoints

### Step 8: Configure Detection Zones

Edit `configs/zones.yaml` to map camera views to sprinkler zones:

1. **Define your cameras:**
   - List each Ring camera you want to monitor
   - Use the exact camera names from Step 6

2. **Map detection zones:**
   - Divide each camera's view into zones
   - Use normalized coordinates (0.0 to 1.0)
   - Example: `x_min: 0.0, x_max: 0.5` = left half of image

3. **Assign sprinkler zones:**
   - Map each detection zone to Rainbird zones
   - Multiple zones can share the same area

**Example zone configuration:**
```yaml
- name: "Front Left Garden"
  camera_id: "front_camera"
  detection_area:
    x_min: 0.0
    y_min: 0.0
    x_max: 0.5
    y_max: 1.0
  sprinkler_zones: [1, 2]
```

## Phase 4: Running the System

### Step 9: Test Run (Dry Run Mode)

First, run in dry-run mode to verify everything works without activating sprinklers:

1. **Ensure dry run is enabled in `configs/zones.yaml`:**
   ```yaml
   settings:
     dry_run: true
   ```

2. **Start the system:**
   ```powershell
   python src/main.py
   ```

3. **Monitor the output:**
   - System will check cameras continuously
   - Detections will be logged
   - "[DRY RUN]" messages show what would happen
   - Press Ctrl+C to stop

### Step 10: Live Deployment

When you're ready to go live:

1. **Disable dry run in `configs/zones.yaml`:**
   ```yaml
   settings:
     dry_run: false
   ```

2. **Review safety settings:**
   - `zone_cooldown`: Minimum time between activations (default: 5 min)
   - `sprinkler_duration`: How long to run (default: 30 sec)
   - `active_hours`: When system is active (default: 8 PM - 6 AM)
   - `detection_confirmation`: Require multiple detections (recommended)

3. **Start the system:**
   ```powershell
   python src/main.py
   ```

## Monitoring & Maintenance

### Logs
- Application logs are written to `logs/deer_deterrent.log`
- Review regularly to see detection patterns

### Fine-tuning

**If you get too many false positives:**
- Increase `min_confidence` in `configs/zones.yaml`
- Enable/adjust `detection_confirmation` settings
- Consider retraining with more varied negative examples

**If missing detections:**
- Lower `min_confidence` threshold
- Check camera positioning and lighting
- Review test results to ensure model is working

**Adding more training data:**
- Add new images to `data/raw/`
- Re-run `python src/data/prepare_dataset.py`
- Re-train: `python src/training/train.py`

## Common Issues

### "No module named 'X'"
- Activate your virtual environment
- Run `pip install -r requirements.txt`

### Ring camera not connecting
- Verify credentials in `.env`
- Check if 2FA is enabled (may need additional setup)
- Ensure Ring app works on your phone

### Rainbird not responding
- Verify controller IP address in `.env`
- Check that controller is on your network
- API endpoints may vary by model

### Poor detection accuracy
- Train for more epochs
- Add more annotated images
- Ensure good variety in training data (different times, angles, lighting)

## Next Steps

Once everything is running smoothly:
- Monitor detection patterns over a few days
- Adjust confidence thresholds as needed
- Fine-tune sprinkler durations
- Add more cameras or zones as needed

## Support

For issues with specific libraries:
- **YOLOv8**: https://docs.ultralytics.com/
- **Ring API**: https://github.com/tchellomello/python-ring-doorbell
- **Rainbird**: Check your controller's documentation

Happy deer deterring! 🦌💦
