# Raspberry Pi Deployment Guide - Deer Deterrent System

This guide will walk you through setting up your Raspberry Pi 4/5 as a dedicated deer deterrent coordinator. The RPi will handle Ring camera events and trigger Rainbird sprinklers when deer are detected.

## Why Raspberry Pi is Perfect for This

**Advantages:**
- ✅ **Low power consumption** - Runs 24/7 for ~$5/year electricity
- ✅ **Always-on reliability** - Purpose-built for automation
- ✅ **Direct network access** - Can receive webhooks from Ring
- ✅ **Fast startup** - No heavy ML loading delays
- ✅ **Easy to maintain** - Simple Linux environment
- ✅ **Wired Ethernet** - More reliable than WiFi for critical automation

**Why wired connection is important:**
- Ring webhooks need reliable delivery (WiFi can drop packets)
- Sprinkler activation is time-sensitive (deer move fast!)
- No WiFi credentials to manage/rotate
- Lower latency for real-time detection → action

---

## Architecture Overview

We'll use a **lightweight coordinator** approach:

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  Ring Camera    │────────▶│  Raspberry Pi    │────────▶│ Rainbird        │
│                 │ webhook │  Coordinator     │   API   │ Sprinkler       │
│ Motion Detected │         │                  │         │ System          │
└─────────────────┘         └──────────────────┘         └─────────────────┘
                                     │
                                     │ Send image
                                     ▼
                            ┌──────────────────┐
                            │ ML Detection     │
                            │ (Cloud or Local) │
                            │                  │
                            │ Returns: Deer?   │
                            └──────────────────┘
```

**How it works:**
1. Ring camera detects motion
2. Ring sends webhook to your RPi
3. RPi downloads snapshot from Ring
4. RPi sends image to ML detector (cloud or local)
5. If deer detected: RPi triggers Rainbird sprinkler
6. RPi logs event to dashboard backend

**ML Detection Options:**
- **Option A (Recommended)**: Cloud-based via Vercel serverless function (fast, reliable)
- **Option B**: Local YOLO on RPi (slower but private, ~10-20 sec processing)

---

## Part 1: Hardware Preparation

### 1.1 What You'll Need

**Required:**
- ✅ Raspberry Pi 4 or 5 (any RAM: 2GB, 4GB, 8GB all work)
- ✅ MicroSD card (16GB minimum, 32GB recommended)
- ✅ Power supply (official RPi PSU recommended)
- ✅ Ethernet cable (Cat5e or Cat6)
- ✅ MicroSD card reader (for your Windows PC)
- ✅ Monitor + HDMI cable + USB keyboard (for initial setup only)

**Optional but helpful:**
- USB-C to USB-A adapter (if your PC doesn't have USB-C)
- Case with cooling fan (RPi can get warm)

### 1.2 Prepare the MicroSD Card

We'll do a **fresh install** of Raspberry Pi OS to ensure a clean environment.

**On your Windows PC:**

1. **Download Raspberry Pi Imager**
   - Visit: https://www.raspberrypi.com/software/
   - Download and install "Raspberry Pi Imager" for Windows
   - Run the installer

2. **Insert MicroSD Card**
   - Use card reader to connect microSD to your PC
   - Note the drive letter (e.g., D:, E:, F:)

3. **Flash the OS**
   - Open **Raspberry Pi Imager**
   - Click **CHOOSE DEVICE** → Select "Raspberry Pi 4" (or 5 if you have that)
   - Click **CHOOSE OS** → Select "Raspberry Pi OS (64-bit)"
     - **Important**: Choose **"Raspberry Pi OS Lite (64-bit)"** - no desktop, smaller/faster
     - Navigate: Other general-purpose OS → Raspberry Pi OS (other) → **Raspberry Pi OS Lite (64-bit)**
   
4. **Configure Settings (CRITICAL STEP)**
   - Click the **gear icon** (⚙️) in bottom-right (or press Ctrl+Shift+X)
   - This opens advanced settings
   
   **Configure these settings:**
   
   ✅ **Enable SSH**
   - Check "Enable SSH"
   - Select "Use password authentication"
   
   ✅ **Set username and password**
   - Username: `pi` (default, or choose your own)
   - Password: Choose a secure password (you'll need this!)
   
   ✅ **Configure WiFi (OPTIONAL - only for initial setup)**
   - SSID: Your WiFi network name
   - Password: Your WiFi password
   - WiFi Country: US
   - **Note**: We'll switch to Ethernet later, but WiFi helps for initial setup
   
   ✅ **Set Locale Settings**
   - Timezone: America/New_York (or your timezone)
   - Keyboard layout: us
   
   ✅ **Hostname** (optional)
   - Set to: `deer-pi` (easier to find on network)
   
   - Click **SAVE**

5. **Write to SD Card**
   - Click **CHOOSE STORAGE** → Select your microSD card
   - Click **WRITE**
   - Confirm warning (this erases the card!)
   - Wait 5-10 minutes for write + verify
   - When complete, click **CONTINUE**
   - **Safely eject** the microSD card from Windows

### 1.3 First Boot

1. **Insert microSD into Raspberry Pi**
   - Power off the RPi if it's on
   - Insert the flashed microSD card

2. **Connect Peripherals (First Boot Only)**
   - Connect monitor via HDMI
   - Connect USB keyboard
   - Connect Ethernet cable to your router/switch
   - **Last step**: Connect power supply
   
3. **Wait for Boot**
   - First boot takes 1-2 minutes
   - You'll see boot messages scroll by
   - Eventually you'll see a login prompt

4. **Log In**
   - Username: `pi` (or what you set in imager)
   - Password: (what you set in imager)
   
5. **Verify Network Connection**
   ```bash
   # Check if connected to network
   ip addr show eth0
   
   # Should show an IP address like:
   # inet 192.168.1.XXX/24
   
   # Note this IP address!
   ```

6. **Test Internet Connection**
   ```bash
   ping -c 4 google.com
   
   # Should see 4 successful replies
   ```

7. **Find Your RPi's IP Address**
   ```bash
   hostname -I
   
   # Shows IP address(es)
   # Note the first one (usually 192.168.1.XXX)
   ```

### 1.4 Enable SSH and Disconnect Monitor

SSH should already be enabled from the imager settings, but let's verify:

```bash
# Check SSH status
sudo systemctl status ssh

# Should show "active (running)"
```

**Now test SSH from your Windows PC:**

```powershell
# From Windows PowerShell
ssh pi@192.168.1.XXX

# Replace XXX with your RPi's IP
# Enter password when prompted
```

**If SSH works, you can now disconnect monitor/keyboard!** From this point forward, everything is done via SSH from your Windows PC.

---

## Part 2: System Setup and Updates

**From your Windows PC (via SSH):**

```powershell
ssh pi@192.168.1.XXX
```

### 2.1 Update System

```bash
# Update package lists
sudo apt update

# Upgrade all packages (this may take 10-15 minutes)
sudo apt upgrade -y

# Clean up old packages
sudo apt autoremove -y
sudo apt autoclean
```

### 2.2 Set Static IP Address (IMPORTANT)

You need a **static IP** so Ring webhooks always reach the same address.

**Option A: Set via Router (RECOMMENDED)**

1. Log into your router's admin panel
2. Find DHCP settings or "LAN" settings
3. Look for "Static DHCP" or "DHCP Reservation"
4. Add reservation:
   - MAC Address: (found with `ip link show eth0` - look for "link/ether")
   - IP Address: Choose one (e.g., 192.168.1.200)
   - Hostname: deer-pi
5. Save and reboot router if needed
6. Reboot RPi: `sudo reboot`
7. Reconnect SSH using the new static IP

**Option B: Set on RPi Directly**

```bash
# Edit network config
sudo nano /etc/dhcpcd.conf

# Add to bottom of file (replace with your network details):
interface eth0
static ip_address=192.168.1.200/24
static routers=192.168.1.1
static domain_name_servers=8.8.8.8 8.8.4.4

# Save: Ctrl+O, Enter, Ctrl+X

# Restart networking
sudo systemctl restart dhcpcd

# Verify new IP
ip addr show eth0
```

**Test connectivity:**
```bash
ping -c 4 8.8.8.8
ping -c 4 google.com
```

### 2.3 Set Timezone

```bash
# Set timezone
sudo timedatectl set-timezone America/New_York

# Verify
timedatectl
```

### 2.4 Install Essential Packages

```bash
# Install useful tools
sudo apt install -y \
  git \
  curl \
  wget \
  vim \
  htop \
  unzip \
  python3-pip \
  python3-venv
```

---

## Part 3: Install Docker

Docker makes deployment and updates much easier.

### 3.1 Install Docker

```bash
# Download Docker install script
curl -fsSL https://get.docker.com -o get-docker.sh

# Run installer
sudo sh get-docker.sh

# Add pi user to docker group (no need for sudo)
sudo usermod -aG docker pi

# Log out and back in for group change to take effect
exit
```

**Reconnect via SSH:**
```powershell
ssh pi@192.168.1.XXX
```

**Verify Docker works:**
```bash
# Check Docker version
docker --version

# Should show: Docker version 24.x.x

# Test Docker (without sudo)
docker run hello-world

# Should download image and show success message
```

### 3.2 Install Docker Compose

```bash
# Install Docker Compose plugin
sudo apt install -y docker-compose-plugin

# Verify
docker compose version

# Should show: Docker Compose version v2.x.x
```

---

## Part 4: Deploy the Coordinator Service

### 4.1 Clone the Repository

```bash
# Navigate to home directory
cd ~

# Clone the repo
git clone https://github.com/rndpig/deer-deterrent.git

# Navigate into it
cd deer-deterrent
```

### 4.2 Create RPi-Specific Directory Structure

```bash
# Create directories for RPi coordinator
mkdir -p rpi-coordinator
mkdir -p rpi-coordinator/logs
mkdir -p rpi-coordinator/data
mkdir -p rpi-coordinator/config
```

### 4.3 Create Coordinator Service

We'll create a lightweight service that:
- Listens for Ring webhooks
- Downloads snapshot from Ring
- Sends to ML detector (cloud or local)
- Triggers Rainbird sprinkler if deer detected

**Create the service file:**

```bash
nano rpi-coordinator/main.py
```

**Add this code:**

```python
#!/usr/bin/env python3
"""
Deer Deterrent Coordinator - Raspberry Pi Service
Handles Ring camera webhooks and Rainbird sprinkler activation
"""

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
import httpx
import os
import logging
from datetime import datetime
from pathlib import Path
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/coordinator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Deer Deterrent Coordinator")

# Configuration from environment variables
CONFIG = {
    "ML_ENDPOINT": os.getenv("ML_ENDPOINT", "http://localhost:8000/api/detect"),
    "RAINBIRD_API": os.getenv("RAINBIRD_API", "http://rainbird-controller.local"),
    "RAINBIRD_ZONE": os.getenv("RAINBIRD_ZONE", "1"),
    "RAINBIRD_DURATION": int(os.getenv("RAINBIRD_DURATION", "30")),  # seconds
    "CONFIDENCE_THRESHOLD": float(os.getenv("CONFIDENCE_THRESHOLD", "0.7")),
    "DASHBOARD_API": os.getenv("DASHBOARD_API", "https://deer-api.rndpig.com:8000"),
    "RING_WEBHOOK_SECRET": os.getenv("RING_WEBHOOK_SECRET", ""),
    "COOLDOWN_SECONDS": int(os.getenv("COOLDOWN_SECONDS", "300")),  # 5 min default
}

# Track last activation to prevent spam
last_activation_time = None


async def download_ring_snapshot(snapshot_url: str) -> bytes:
    """Download snapshot from Ring camera"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(snapshot_url)
            response.raise_for_status()
            logger.info(f"Downloaded snapshot: {len(response.content)} bytes")
            return response.content
    except Exception as e:
        logger.error(f"Failed to download snapshot: {e}")
        raise


async def detect_deer(image_bytes: bytes) -> dict:
    """Send image to ML detector and get results"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": ("snapshot.jpg", image_bytes, "image/jpeg")}
            response = await client.post(CONFIG["ML_ENDPOINT"], files=files)
            response.raise_for_status()
            result = response.json()
            logger.info(f"ML detection result: {result}")
            return result
    except Exception as e:
        logger.error(f"ML detection failed: {e}")
        raise


async def activate_sprinkler(zone: str, duration: int):
    """Activate Rainbird sprinkler zone"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            payload = {
                "zone": zone,
                "duration": duration
            }
            # This will be updated once we reverse-engineer Rainbird API
            response = await client.post(
                f"{CONFIG['RAINBIRD_API']}/activate",
                json=payload
            )
            response.raise_for_status()
            logger.info(f"Activated sprinkler zone {zone} for {duration}s")
            return True
    except Exception as e:
        logger.error(f"Failed to activate sprinkler: {e}")
        return False


async def log_detection(detection_data: dict):
    """Log detection to dashboard backend"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{CONFIG['DASHBOARD_API']}/api/detections",
                json=detection_data
            )
            logger.info("Logged detection to dashboard")
    except Exception as e:
        logger.error(f"Failed to log detection: {e}")


async def process_motion_event(snapshot_url: str):
    """Background task: Process Ring motion event"""
    global last_activation_time
    
    try:
        # Download snapshot
        logger.info(f"Processing motion event: {snapshot_url}")
        image_bytes = await download_ring_snapshot(snapshot_url)
        
        # Save snapshot locally
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_path = Path(f"/app/data/snapshots/{timestamp}.jpg")
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes(image_bytes)
        logger.info(f"Saved snapshot: {snapshot_path}")
        
        # Run ML detection
        detection_result = await detect_deer(image_bytes)
        
        # Check if deer detected with sufficient confidence
        deer_detected = False
        highest_confidence = 0.0
        
        if "detections" in detection_result:
            for det in detection_result["detections"]:
                if det.get("class") == "deer" and det.get("confidence", 0) >= CONFIG["CONFIDENCE_THRESHOLD"]:
                    deer_detected = True
                    highest_confidence = max(highest_confidence, det["confidence"])
        
        logger.info(f"Deer detected: {deer_detected}, Confidence: {highest_confidence:.2f}")
        
        # If deer detected, activate sprinkler (with cooldown)
        if deer_detected:
            now = datetime.now()
            
            # Check cooldown
            if last_activation_time:
                elapsed = (now - last_activation_time).total_seconds()
                if elapsed < CONFIG["COOLDOWN_SECONDS"]:
                    logger.info(f"Cooldown active: {elapsed:.0f}s elapsed, {CONFIG['COOLDOWN_SECONDS']}s required")
                    return
            
            # Activate sprinkler
            success = await activate_sprinkler(
                CONFIG["RAINBIRD_ZONE"],
                CONFIG["RAINBIRD_DURATION"]
            )
            
            if success:
                last_activation_time = now
                logger.info("✓ Sprinkler activated successfully")
            
            # Log to dashboard
            await log_detection({
                "timestamp": timestamp,
                "confidence": highest_confidence,
                "sprinkler_activated": success,
                "snapshot_path": str(snapshot_path)
            })
    
    except Exception as e:
        logger.error(f"Error processing motion event: {e}", exc_info=True)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Deer Deterrent Coordinator",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "config": {
            "ml_endpoint": CONFIG["ML_ENDPOINT"],
            "rainbird_zone": CONFIG["RAINBIRD_ZONE"],
            "cooldown_seconds": CONFIG["COOLDOWN_SECONDS"],
        },
        "last_activation": last_activation_time.isoformat() if last_activation_time else None
    }


@app.post("/webhook/ring")
async def ring_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive webhook from Ring camera
    
    Expected payload:
    {
        "event": "motion",
        "timestamp": "2025-11-02T19:30:00Z",
        "camera_id": "abc123",
        "snapshot_url": "https://ring.com/snapshots/xyz.jpg"
    }
    """
    try:
        payload = await request.json()
        logger.info(f"Received Ring webhook: {payload}")
        
        # Validate webhook (if secret is configured)
        if CONFIG["RING_WEBHOOK_SECRET"]:
            # Add signature validation here
            pass
        
        # Extract snapshot URL
        snapshot_url = payload.get("snapshot_url")
        if not snapshot_url:
            logger.error("No snapshot_url in webhook payload")
            return JSONResponse(
                status_code=400,
                content={"error": "Missing snapshot_url"}
            )
        
        # Process in background (don't block webhook response)
        background_tasks.add_task(process_motion_event, snapshot_url)
        
        return {"status": "accepted", "message": "Processing motion event"}
    
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    snapshot_dir = Path("/app/data/snapshots")
    snapshot_count = len(list(snapshot_dir.glob("*.jpg"))) if snapshot_dir.exists() else 0
    
    return {
        "total_snapshots": snapshot_count,
        "last_activation": last_activation_time.isoformat() if last_activation_time else None,
        "cooldown_seconds": CONFIG["COOLDOWN_SECONDS"],
        "config": CONFIG
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
```

**Save**: Ctrl+O, Enter, Ctrl+X

### 4.4 Create Requirements File

```bash
nano rpi-coordinator/requirements.txt
```

**Add:**
```
fastapi==0.115.0
uvicorn[standard]==0.32.0
httpx==0.27.2
python-multipart==0.0.17
```

**Save**: Ctrl+O, Enter, Ctrl+X

### 4.5 Create Docker Compose Configuration

```bash
nano rpi-coordinator/docker-compose.yml
```

**Add:**

```yaml
version: '3.8'

services:
  coordinator:
    image: python:3.11-slim
    container_name: deer-coordinator
    restart: unless-stopped
    working_dir: /app
    
    volumes:
      - ./main.py:/app/main.py
      - ./requirements.txt:/app/requirements.txt
      - ./logs:/app/logs
      - ./data:/app/data
      - ./config:/app/config
    
    ports:
      - "5000:5000"
    
    environment:
      - PYTHONUNBUFFERED=1
      - TZ=America/New_York
      
      # ML Detection endpoint
      # Option A: Cloud-based (Vercel serverless - we'll create this)
      - ML_ENDPOINT=https://deer.rndpig.com/api/detect
      
      # Option B: Local YOLO on RPi (slower)
      # - ML_ENDPOINT=http://localhost:8000/api/detect
      
      # Rainbird API (we'll configure this after reverse-engineering)
      - RAINBIRD_API=http://192.168.1.XXX
      - RAINBIRD_ZONE=1
      - RAINBIRD_DURATION=30
      
      # Dashboard backend
      - DASHBOARD_API=https://deer-api.rndpig.com:8000
      
      # Detection settings
      - CONFIDENCE_THRESHOLD=0.75
      - COOLDOWN_SECONDS=300
      
      # Ring webhook secret (optional)
      - RING_WEBHOOK_SECRET=your-secret-here
    
    command: >
      bash -c "
        echo '=== Starting Deer Deterrent Coordinator ===' &&
        pip install --no-cache-dir -q -r requirements.txt &&
        python main.py
      "
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s

networks:
  default:
    name: deer-network
```

**Save**: Ctrl+O, Enter, Ctrl+X

### 4.6 Deploy the Coordinator

```bash
# Navigate to coordinator directory
cd ~/deer-deterrent/rpi-coordinator

# Start the service
docker compose up -d

# Watch logs
docker compose logs -f coordinator

# You should see:
# coordinator | === Starting Deer Deterrent Coordinator ===
# coordinator | INFO:     Started server process [1]
# coordinator | INFO:     Uvicorn running on http://0.0.0.0:5000
```

**Press Ctrl+C to exit logs** (container keeps running)

### 4.7 Test the Coordinator

```bash
# Test health endpoint
curl http://localhost:5000/health

# Should return JSON with status: healthy

# Test from Windows PC (replace with RPi IP)
curl http://192.168.1.200:5000/health
```

---

## Part 5: Configure Ring Webhooks

### 5.1 Understanding Ring Webhook Options

Ring doesn't officially support webhooks, but we have a few options:

**Option A: Use ring-mqtt Bridge (RECOMMENDED)**
- Install ring-mqtt on RPi
- It connects to Ring API and exposes MQTT topics
- We can subscribe to motion events
- No 2FA issues once initially configured

**Option B: Use Home Assistant Ring Integration**
- Requires Home Assistant on RPi
- Ring integration provides motion sensors
- Can trigger automations

**Option C: Ring.com Developer API**
- Requires Ring Partner account (hard to get)
- Not practical for personal use

**Let's use Option A (ring-mqtt)** - it's the most reliable.

### 5.2 Install ring-mqtt

```bash
# Create directory for ring-mqtt
mkdir -p ~/ring-mqtt
cd ~/ring-mqtt

# Create docker-compose.yml
nano docker-compose.yml
```

**Add:**

```yaml
version: '3.8'

services:
  ring-mqtt:
    image: tsightler/ring-mqtt:latest
    container_name: ring-mqtt
    restart: unless-stopped
    
    volumes:
      - ./data:/data
    
    ports:
      - "8554:8554"  # RTSP server
      - "55123:55123"  # Web UI
    
    environment:
      - TZ=America/New_York
      - RINGTOKEN=  # We'll set this after initial setup
      - MQTTHOST=mosquitto
      - MQTTPORT=1883
    
    depends_on:
      - mosquitto
  
  mosquitto:
    image: eclipse-mosquitto:latest
    container_name: mosquitto
    restart: unless-stopped
    
    volumes:
      - ./mosquitto/config:/mosquitto/config
      - ./mosquitto/data:/mosquitto/data
      - ./mosquitto/log:/mosquitto/log
    
    ports:
      - "1883:1883"
      - "9001:9001"

networks:
  default:
    name: ring-network
```

**Save**: Ctrl+O, Enter, Ctrl+X

### 5.3 Configure Mosquitto MQTT Broker

```bash
# Create mosquitto config directory
mkdir -p mosquitto/config mosquitto/data mosquitto/log

# Create config file
nano mosquitto/config/mosquitto.conf
```

**Add:**

```
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
```

**Save**: Ctrl+O, Enter, Ctrl+X

### 5.4 Start ring-mqtt

```bash
# Start services
docker compose up -d

# Watch logs for ring-mqtt
docker compose logs -f ring-mqtt

# You'll see instructions for getting Ring token
```

### 5.5 Get Ring API Token

**Follow the instructions in ring-mqtt logs:**

1. Open browser to: `http://192.168.1.200:55123` (replace with your RPi IP)
2. You'll see ring-mqtt web UI
3. Click "Get Ring Token"
4. Log into your Ring account
5. Complete 2FA (this is a ONE-TIME setup)
6. Copy the token provided
7. Update docker-compose.yml with the token:

```bash
nano docker-compose.yml

# Find the RINGTOKEN line and add your token:
# - RINGTOKEN=your-token-here

# Save and restart
docker compose down
docker compose up -d
```

### 5.6 Subscribe to Ring Motion Events

Now we need to connect our coordinator to MQTT to receive Ring events.

**Update coordinator to listen to MQTT:**

```bash
cd ~/deer-deterrent/rpi-coordinator

# Add paho-mqtt to requirements
nano requirements.txt
```

**Add this line:**
```
paho-mqtt==2.1.0
```

**Save**: Ctrl+O, Enter, Ctrl+X

**Update main.py to include MQTT listener** (I'll provide this code next).

---

## Part 6: Configure Rainbird Integration

### 6.1 Find Your Rainbird Controller

**Rainbird controllers typically connect via:**
- WiFi module (LNK WiFi Module)
- Ethernet (some models)

**Find the IP address:**

```bash
# Scan your local network for Rainbird
sudo nmap -sn 192.168.1.0/24 | grep -i rainbird

# Or check your router's connected devices list
```

### 6.2 Reverse-Engineer Rainbird API

**We need to sniff the API calls the Rainbird mobile app makes.**

**Tools we can use:**
1. Wireshark on PC (capture network traffic)
2. mitmproxy (intercept HTTPS)
3. Rainbird Rain Cloud API (if your model supports cloud)

**I'll need to know:**
- What Rainbird model do you have?
- Does it have WiFi/LNK module?
- Can you access it via web interface?

**Once we know the model, I'll provide specific API instructions.**

---

## Part 7: ML Detection Options

### Option A: Cloud-Based Detection (Vercel Serverless)

**Pros:**
- Fast (1-2 second processing)
- No RPi resources needed
- Always available
- Easy to update model

**Cons:**
- Requires internet
- Snapshot uploaded to cloud (privacy concern?)
- Vercel free tier limits (~100 invocations/day)

**Implementation:** I'll create a Vercel serverless function for you.

### Option B: Local Detection on RPi

**Pros:**
- Fully private
- No internet needed
- Unlimited detections

**Cons:**
- Slow (10-20 seconds on RPi 4/5)
- Uses 2-3GB RAM during detection
- Requires torch/YOLO installation

**Implementation:** Similar to QNAP setup but optimized for RPi.

**Which do you prefer?**

---

## Part 8: Router Port Forwarding (For Ring Webhooks)

If Ring needs to send webhooks to your RPi from outside your network:

1. Log into your router
2. Find "Port Forwarding" or "Virtual Servers"
3. Add rule:
   - External Port: 5000
   - Internal IP: 192.168.1.200 (your RPi)
   - Internal Port: 5000
   - Protocol: TCP
4. Save and test with: https://www.yougetsignal.com/tools/open-ports/

**Note:** ring-mqtt runs locally, so you may NOT need port forwarding! The ring-mqtt service polls Ring's cloud API.

---

## Part 9: Testing the Full Stack

### 9.1 Manual Test

```bash
# Simulate a Ring motion event
curl -X POST http://localhost:5000/webhook/ring \
  -H "Content-Type: application/json" \
  -d '{
    "event": "motion",
    "timestamp": "2025-11-02T20:00:00Z",
    "camera_id": "test",
    "snapshot_url": "https://example.com/test.jpg"
  }'
```

### 9.2 Monitor Logs

```bash
cd ~/deer-deterrent/rpi-coordinator
docker compose logs -f coordinator
```

### 9.3 Check Dashboard

Open: https://deer.rndpig.com

You should see the detection logged in the History tab.

---

## Part 10: Maintenance and Troubleshooting

### Daily Operations

**Check status:**
```bash
docker ps
```

**View logs:**
```bash
docker compose logs -f coordinator
```

**Restart service:**
```bash
docker compose restart coordinator
```

**Update code:**
```bash
cd ~/deer-deterrent
git pull
cd rpi-coordinator
docker compose restart
```

### Auto-Start on Boot

Docker containers with `restart: unless-stopped` automatically start on boot. No additional configuration needed!

### Troubleshooting

**Coordinator not starting:**
```bash
docker compose logs coordinator
# Check for errors in output
```

**No Ring events received:**
```bash
cd ~/ring-mqtt
docker compose logs ring-mqtt
# Verify Ring connection
```

**Sprinkler not activating:**
```bash
# Check Rainbird connectivity
ping 192.168.1.XXX  # Rainbird IP
```

---

## Next Steps

**Let me know:**

1. ✅ **Can you find your RPi and get it powered on?**
   - I'll walk you through the setup step-by-step

2. ✅ **Which ML detection option do you prefer?**
   - Cloud (fast, Vercel serverless)
   - Local (private, slower)

3. ✅ **What Rainbird model/controller do you have?**
   - I'll reverse-engineer the API for that specific model

4. ✅ **Do you want help with ring-mqtt setup?**
   - I can guide you through the token process

This RPi approach will be much simpler and more reliable than the QNAP setup. The coordinator service is lightweight and purpose-built for this exact use case!
