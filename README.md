# Deer Deterrent System

An AI-powered deer detection and deterrent system that monitors Ring camera feeds and automatically activates sprinklers to deter deer from your property.

## Overview

This project uses machine learning to detect deer in real-time from Ring camera footage and automatically triggers Rainbird irrigation zones to humanely deter them from eating plants and causing damage.

## 🚀 Quick Start

Get up and running in under 30 minutes:

1. **📖 Read the Quick Start Guide:** [`QUICKSTART.md`](QUICKSTART.md) - Fastest path to deployment
2. **📚 Full Documentation:** [`DEPLOYMENT.md`](DEPLOYMENT.md) - Comprehensive setup guide
3. **✅ Track Progress:** [`CHECKLIST.md`](CHECKLIST.md) - Step-by-step deployment checklist

## ✨ Key Features

- **⚡ Sub-Second Detection** - Motion detected and processed in <1 second
- **🎯 Accurate ML Model** - Custom YOLOv8 model trained on deer imagery
- **💧 Smart Irrigation** - Integrates with Rainbird controllers for targeted deterrence
- **📊 Real-Time Dashboard** - Monitor detections, view snapshots, track activity
- **🔒 Privacy-First** - All processing runs locally on your hardware
- **🎨 Easy Setup** - Docker Compose handles all dependencies

## System Architecture

The system consists of 7 Docker containers working together:

1. **Ring-MQTT** - Bridges Ring cameras to MQTT broker
2. **MQTT Broker (Mosquitto)** - Message bus for camera events
3. **Coordinator** - Orchestrates detection workflow and sprinkler control
4. **ML Detector** - YOLOv8 model for deer detection
5. **Backend API** - FastAPI service for data persistence
6. **PostgreSQL Database** - Stores detection history
7. **Frontend Dashboard** - React web interface for monitoring

### Event Flow

```
Ring Camera → Ring-MQTT → MQTT Broker → Coordinator → ML Detector
                                              ↓
                                    Rainbird Controller
                                              ↓
                                       Backend API → Database
                                              ↓
                                     Frontend Dashboard
```

**Detection Timeline:**
- T+0s: Motion detected by Ring camera
- T+1s: Snapshot cached via MQTT
- T+1.2s: ML analysis completed
- T+1.5s: Sprinkler activated (if deer detected)
- T+2s: Event logged to database

## Project Structure

```
deer-deterrent/
├── docker-compose.yml           # Main deployment configuration
├── Dockerfile.coordinator       # Coordinator service
├── Dockerfile.ml-detector       # ML detection service
├── .env.example                 # Environment template
│
├── backend/                     # Backend API
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
│
├── frontend/                    # React dashboard
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│
├── configs/                     # Configuration
│   ├── training_config.yaml
│   └── zones.yaml
│
├── models/                      # ML models
│   └── deer_detector_best.pt
│
├── notebooks/                   # Training notebooks
│   └── train_deer_detector_colab.ipynb
│
├── scripts/                     # Utility scripts
│   ├── demo_system.py
│   ├── setup_ring_auth.py
│   └── discover_rainbird_api.py
│
└── docs/                        # Additional documentation
```

## Prerequisites

- **Hardware:** Any x86_64 server/PC (tested on Dell OptiPlex 7050)
- **OS:** Ubuntu 22.04 LTS (or similar Linux distribution)
- **Software:** Docker, Docker Compose
- **Ring Account:** With at least one Ring camera
- **Network:** Local network access to Ring cameras and Rainbird controller (optional)

## Quick Installation

```bash
# Clone repository
git clone https://github.com/rndpig/deer-deterrent.git
cd deer-deterrent

# Copy and configure environment
cp .env.example .env
# Edit .env with your Ring credentials

# Start all services
docker compose up -d

# View logs
docker compose logs -f
```

For detailed setup instructions, see [`QUICKSTART.md`](QUICKSTART.md)

## Configuration

Edit `.env` with your specific settings:

```bash
# Ring Camera Configuration
RING_REFRESH_TOKEN=your_token_here
RING_TOKEN=your_token_here

# Rainbird Controller (optional - for sprinkler activation)
RAINBIRD_IP=192.168.1.100
RAINBIRD_PASSWORD=your_password

# ML Detection Settings
CONFIDENCE_THRESHOLD=0.75
COOLDOWN_SECONDS=300

# Active Hours (24-hour format)
ACTIVE_HOURS_START=0
ACTIVE_HOURS_END=24
```

## Usage

### View Dashboard
Access the web dashboard at `http://your-server-ip:3000` to:
- View real-time detection events
- Browse detection history with snapshots
- Monitor camera status
- Configure settings

### Command Line Management

```bash
# View all logs
docker compose logs -f

# View specific service
docker compose logs -f coordinator

# Restart a service
docker compose restart coordinator

# Stop all services
docker compose down

# Update and restart
git pull && docker compose build && docker compose up -d
```

## Safety & Features

- ✅ **Configurable cooldown periods** - Prevent excessive sprinkler activation
- ✅ **Time-based rules** - Only activate during specified hours
- ✅ **Confidence thresholds** - Reduce false positives
- ✅ **Dry-run mode** - Test without activating sprinklers (set `RAINBIRD_IP=""`)
- ✅ **Historical logging** - Track all detections with timestamps and images

## Performance

**Tested on Dell OptiPlex 7050 (i7-6700, 16GB RAM):**
- Motion detection: <1 second
- ML inference: ~200ms
- Total response time: ~1.5 seconds from motion to sprinkler activation

## Troubleshooting

See [`DEPLOYMENT.md`](DEPLOYMENT.md) for detailed troubleshooting steps, including:
- Ring authentication issues
- MQTT connectivity problems
- ML detector performance tuning
- Database connection errors

## Training Your Own Model

The included model (`models/deer_detector_best.pt`) is trained on deer imagery. To retrain or fine-tune:

1. See [`notebooks/train_deer_detector_colab.ipynb`](notebooks/train_deer_detector_colab.ipynb)
2. Upload to Google Colab (free GPU available)
3. Follow notebook instructions to train on your own dataset
4. Download trained model and replace `models/deer_detector_best.pt`

## Contributing

Contributions welcome! This is an active project. Please open an issue to discuss major changes.

## License

MIT License - See LICENSE file for details

## Acknowledgments

- Built with YOLOv8 for object detection
- Ring-MQTT bridge by @tsightler
- Inspired by the need to protect gardens humanely
- Special thanks to the open-source community

## Project Status

✅ **Production Ready** - System is deployed and actively logging deer detections. Sprinkler integration tested and functional.
