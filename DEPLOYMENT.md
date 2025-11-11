# Dell OptiPlex Linux Deployment Guide
## Deer Deterrent System - All-in-One Server Setup

This guide will walk you through setting up your Dell OptiPlex 9020 as a complete deer deterrent server running Ubuntu Server 24.04 LTS with Docker.

---

## Why Dell OptiPlex is Perfect for This Project

**Your Hardware:**
- Intel Core i7-4790 (4 cores @ 3.6GHz)
- 16GB RAM
- 256GB SSD
- AMD Radeon R5 240 (1GB)
- Intel vPro Network
- 85% efficient power supply

**Performance Benefits:**
- ✅ **ML Inference**: 2-5 seconds (vs 10-20 on RPi)
- ✅ **All-in-One**: Frontend + Backend + ML + Database on one machine
- ✅ **16GB RAM**: Plenty for YOLO models without memory pressure
- ✅ **SSD Storage**: Fast snapshot saves and log writes
- ✅ **Always-On Cost**: ~$40/year (~$3/month)
- ✅ **Future-Ready**: Can handle heavier models and additional services

---

## Table of Contents

1. [Prerequisites](#part-1-prerequisites)
2. [Prepare Ubuntu Installation Media](#part-2-prepare-ubuntu-installation-media)
3. [BIOS Configuration](#part-3-bios-configuration)
4. [Install Ubuntu Server](#part-4-install-ubuntu-server)
5. [Initial System Configuration](#part-5-initial-system-configuration)
6. [Install Docker](#part-6-install-docker)
7. [Deploy Deer Deterrent System](#part-7-deploy-deer-deterrent-system)
8. [Configure Services](#part-8-configure-services)
9. [Testing and Validation](#part-9-testing-and-validation)
10. [Maintenance and Troubleshooting](#part-10-maintenance-and-troubleshooting)

---

## Part 1: Prerequisites

### What You'll Need

**Hardware:**
- ✅ Dell OptiPlex 9020 (your machine!)
- ✅ Monitor + HDMI/DisplayPort cable
- ✅ USB keyboard + mouse
- ✅ USB flash drive (8GB minimum) - will be erased!
- ✅ Ethernet cable connected to router
- ✅ Your Windows PC (for creating installation media)

**Software:**
- ✅ Ubuntu Server 24.04 LTS ISO (we'll download)
- ✅ Rufus (USB creator tool - we'll download)

**Information to Have Ready:**
- ✅ Your WiFi network name/password (optional backup)
- ✅ Ring account credentials
- ✅ Rainbird controller IP address (or we'll find it)
- ✅ Router admin access (for static IP configuration)

**Time Required:**
- Installation: 30-45 minutes
- Configuration: 30-45 minutes
- **Total: ~1.5 hours** (mostly hands-off)

---

## Part 2: Prepare Ubuntu Installation Media

### 2.1 Download Ubuntu Server

**On your Windows PC:**

1. Open browser and go to: https://ubuntu.com/download/server
2. Click **"Download Ubuntu Server 24.04 LTS"**
3. Save the ISO file (filename: `ubuntu-24.04-live-server-amd64.iso`)
4. Size: ~2.6GB, download takes 5-15 minutes depending on connection

**While downloading, proceed to download Rufus...**

### 2.2 Download Rufus (USB Creation Tool)

1. Go to: https://rufus.ie/
2. Click **"Rufus 4.x Portable"** (no installation needed)
3. Save `rufus-4.x.exe` to your Downloads folder
4. **Note**: You may see Windows SmartScreen warning - click "More info" → "Run anyway" (Rufus is safe and widely used)

### 2.3 Create Bootable USB Drive

**⚠️ WARNING: This will ERASE ALL DATA on the USB drive!**

1. **Insert USB drive** into your Windows PC
   - Make sure it has nothing important on it!
   - Note which drive letter it gets (e.g., D:, E:, F:)

2. **Run Rufus**
   - Double-click `rufus-4.x.exe`
   - Click "Yes" if Windows asks for administrator permission

3. **Configure Rufus Settings:**
   
   | Setting | Value |
   |---------|-------|
   | **Device** | Select your USB drive |
   | **Boot selection** | Click "SELECT" → Choose the Ubuntu ISO you downloaded |
   | **Partition scheme** | GPT |
   | **Target system** | UEFI (non CSM) |
   | **Volume label** | UBUNTU_SERVER (optional) |
   | **File system** | FAT32 (default) |
   | **Cluster size** | 4096 bytes (default) |

4. **Start Writing**
   - Click **"START"**
   - If prompted about "ISOHybrid image", select **"Write in DD Image mode"** → OK
   - If prompted about "Download required" for Syslinux, click **"Yes"**
   - Confirm warning about data destruction: **"OK"**
   - Wait 5-10 minutes for writing + verification

5. **Verify Success**
   - Rufus shows "READY" in green status bar
   - Click **"CLOSE"**
   - **Safely eject USB drive**: Right-click drive in File Explorer → "Eject"

**✓ You now have a bootable Ubuntu Server USB drive!**

---

## Part 3: BIOS Configuration

### 3.1 Access Dell BIOS Setup

1. **Connect peripherals to Dell:**
   - Monitor → DisplayPort or HDMI
   - USB keyboard → rear USB port
   - USB mouse → rear USB port
   - Ethernet cable → network port
   - Ubuntu USB drive → **front USB port**
   - Power cable → wall outlet

2. **Power on and enter BIOS:**
   - Press the power button
   - **IMMEDIATELY start tapping F2** repeatedly (once per second)
   - You'll see the Dell logo, then BIOS setup screen
   - **If you miss it**: Power off, try again

### 3.2 Configure Boot Order

**Navigate using Arrow Keys, Enter to select, Esc to go back:**

1. **In BIOS Main Menu:**
   - Look for **"Boot Sequence"** or **"Boot"** tab
   - Press Enter

2. **Set Boot Order:**
   - Find **"Boot List Option"** → Set to **"UEFI"**
   - Find **"Boot Sequence"**:
     - **1st Device**: USB Storage (your Ubuntu USB)
     - **2nd Device**: SATA Hard Drive (your SSD)
   - Use +/- keys or Page Up/Down to reorder

3. **Disable Secure Boot (Important!):**
   - Navigate to **"Secure Boot"** section
   - Set **"Secure Boot Enable"** → **"Disabled"**
   - (Linux will work, but disabling avoids potential driver issues)

4. **Recommended Settings (Optional but helpful):**
   - **"SATA Operation"**: AHCI (should be default)
   - **"Intel Virtualization"**: Enabled (helps with Docker)
   - **"VT for Direct I/O"**: Enabled (helps with Docker)
   - **"Wake on LAN"**: Enabled (useful for remote wake-up later)

5. **Save and Exit:**
   - Press **F10** (or navigate to "Save & Exit")
   - Confirm: **"Yes"**
   - Computer will reboot from USB

---

## Part 4: Install Ubuntu Server

### 4.1 Boot Ubuntu Installer

After BIOS saves and reboots, you'll see:

1. **GRUB Boot Menu:**
   - Select **"Try or Install Ubuntu Server"** (usually default)
   - Press **Enter**
   - Wait 30-60 seconds for installer to load

2. **Language Selection:**
   - Arrow keys to select **"English"**
   - Press **Enter**

### 4.2 Installer Configuration

**Follow these screens carefully:**

#### Screen 1: Installer Update
- **"Update to the new installer"** → Select **"Continue without updating"**
- (Updating can cause issues, stock installer is fine)
- Press **Enter**

#### Screen 2: Keyboard Configuration
- **Layout**: English (US)
- **Variant**: English (US)
- Press **Enter** on "Done"

#### Screen 3: Choose Installation Type
- Select **"Ubuntu Server"** (default)
- Press **Enter** on "Done"

#### Screen 4: Network Connections

This is important for getting a static IP:

- You should see **"enp0s25"** or similar (Intel network adapter)
- It should show **"DHCPv4"** and an IP address like `192.168.1.XXX`
- **Write down this IP address!** (You'll configure static later)
- Press **Enter** on "Done"

#### Screen 5: Configure Proxy
- Leave blank (unless you have a corporate proxy)
- Press **Enter** on "Done"

#### Screen 6: Configure Ubuntu Archive Mirror
- Leave default: `http://us.archive.ubuntu.com/ubuntu`
- Press **Enter** on "Done"

#### Screen 7: Guided Storage Configuration

**⚠️ IMPORTANT: This will ERASE your 256GB SSD!**

Make sure you've backed up any data you need from this drive!

- Select **"Use an entire disk"**
- Select your **256GB SSD** (should be listed as Samsung or Hynix SSD)
- ✅ Check **"Set up this disk as an LVM group"**
- ⬜ UNCHECK "Encrypt the LVM group" (not needed for this project)
- Press **Enter** on "Done"
- Review the partition layout:
  - `/boot` partition: 2GB
  - `/` (root) partition: ~250GB
- Press **Enter** on "Done"
- **Confirm destructive action**: Select **"Continue"** → Enter

#### Screen 8: Profile Setup

**Create your user account:**

- **Your name**: Enter your full name (e.g., "John Smith")
- **Your server's name**: `dilger-server` (or anything you like)
- **Pick a username**: `rndpig` (or your preferred username)
- **Choose a password**: Use a strong password (WRITE IT DOWN!)
- **Confirm your password**: Re-enter password

Press **Enter** on "Done"

#### Screen 9: Upgrade to Ubuntu Pro
- Select **"Skip for now"**
- Press **Enter**
- (Ubuntu Pro is for enterprise support, not needed)

#### Screen 10: SSH Setup

**✓ IMPORTANT: Enable SSH!**

- **Arrow down** to highlight **"Install OpenSSH server"**
- Press **Spacebar** to check the box: `[X]`
- ⬜ Leave "Import SSH identity" unchecked
- Press **Enter** on "Done"

#### Screen 11: Featured Server Snaps
- Leave all unchecked (we'll install Docker manually for better control)
- Press **Enter** on "Done"

### 4.3 Wait for Installation

- You'll see progress bars:
  - "Downloading and installing security updates..."
  - "Installing system..."
  - "Running 'curtin' installation..."
- **Time**: 10-15 minutes
- ☕ Grab a coffee!

### 4.4 Complete Installation

When you see **"Install complete!"**:

1. Press **Enter** on "Reboot Now"
2. You'll see: **"Please remove the installation medium, then press ENTER"**
3. **Remove the USB drive** from the front port
4. Press **Enter**
5. System will reboot

**You should see boot messages, then:**
```
Ubuntu 24.04 LTS dilger-server tty1

dilger-server login: _
```

**✓ Ubuntu Server is now installed!**

---

## Part 5: Initial System Configuration

### 5.1 First Login

At the login prompt:

```
dilger-server login: rndpig
Password: [your password]
```

**You'll see:**
```
Welcome to Ubuntu 24.04 LTS (GNU/Linux 6.8.0-x-generic x86_64)

 * Documentation:  https://help.ubuntu.com
 * Management:     https://landscape.canonical.com
 * Support:        https://ubuntu.com/pro

The programs included with the Ubuntu system are free software;
the exact distribution terms for each program are described in the
individual files in /usr/share/doc/*/copyright.

rndpig@dilger-server:~$
```

**✓ You're in!**

### 5.2 Update System

**Run these commands:**

```bash
# Update package lists
sudo apt update

# You'll be prompted for your password (type it, won't show on screen)
# Output shows: "Reading package lists... Done"

# Upgrade all packages (takes 5-10 minutes)
sudo apt upgrade -y

# Lots of output will scroll by, this is normal
# Wait for it to complete and return to prompt

# Install essential tools
sudo apt install -y curl wget git nano htop net-tools

# Clean up
sudo apt autoremove -y
sudo apt autoclean
```

### 5.3 Find Your IP Address

```bash
# Show network configuration
ip addr show

# Look for "enp0s25" or similar:
# Example output:
# 2: eno1: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
#     link/ether 00:11:22:33:44:55 brd ff:ff:ff:ff:ff:ff
#     inet 192.168.7.215/24 brd 192.168.7.255 scope global dynamic eno1
#            ^^^^^^^^^^^^ THIS IS YOUR IP ADDRESS!
#     valid_lft 86392sec preferred_lft 86392sec

# Write down your IP address (e.g., 192.168.7.215)
```

### 5.4 Set Static IP Address

**Option A: Configure via Netplan (Recommended)**

```bash
# List network interfaces
ls /sys/class/net/

# You should see: eno1 (or similar), lo

# Edit netplan configuration
sudo nano /etc/netplan/50-cloud-init.yaml
```

**You'll see something like:**

```yaml
network:
    ethernets:
        eno1:
            dhcp4: true
    version: 2
```

**Change to (replace IPs with your network's values):**

```yaml
network:
    ethernets:
        eno1:
            dhcp4: no
            addresses:
                - 192.168.7.200/24
            routes:
                - to: default
                  via: 192.168.7.1
            nameservers:
                addresses:
                    - 192.168.7.1
    version: 2
```

**Key values to customize:**
- `192.168.7.200` - Your chosen static IP (pick one not in use!)
- `192.168.7.1` - Your router's IP
- `192.168.7.1` - DNS server (using your router)

**Save and exit:**
- Press `Ctrl+O` to save
- Press `Enter` to confirm filename
- Press `Ctrl+X` to exit

**Apply the configuration:**

```bash
# Test the configuration first (safe, won't break anything)
sudo netplan try

# You'll see: "Do you want to keep these settings?"
# If network still works, press ENTER within 120 seconds
# If you lose connection, wait 120 seconds and it reverts

# If everything works, apply permanently:
sudo netplan apply

# Verify new IP
ip addr show eno1

# Should now show your static IP: 192.168.7.200
```

**Option B: Configure via Router DHCP Reservation (Alternative)**

If you prefer, you can set a static DHCP reservation in your router instead:

1. Log into your router (usually http://192.168.7.1)
2. Find "DHCP Settings" or "LAN Settings"
3. Look for "DHCP Reservation" or "Static DHCP"
4. Add reservation:
   - **MAC Address**: (run `ip link show eno1` - copy the `link/ether` value)
   - **IP Address**: 192.168.7.200
   - **Hostname**: dilger-server
5. Save and reboot router

### 5.5 Test SSH from Windows

**On your Windows PC, open PowerShell:**

```powershell
# Test connection (replace with your static IP)
ssh rndpig@192.168.7.200

# First time you'll see:
# "The authenticity of host '192.168.7.200' can't be established."
# Type: yes [Enter]

# Enter your password when prompted

# You should now be logged into the Dell from Windows!
```

**✓ From now on, you can work from your Windows PC via SSH!**

**Optional: Disconnect monitor/keyboard from Dell**

The Dell can now run "headless" (no monitor). Keep it connected to:
- ✅ Power
- ✅ Ethernet
- ❌ Monitor/keyboard (can disconnect!)

### 5.6 Configure Timezone

```bash
# Check current timezone
timedatectl

# Set to your timezone (example: Eastern Time)
sudo timedatectl set-timezone America/New_York

# Or find your timezone:
timedatectl list-timezones | grep -i chicago  # Central
timedatectl list-timezones | grep -i denver   # Mountain
timedatectl list-timezones | grep -i los      # Pacific

# Set it:
sudo timedatectl set-timezone America/Chicago  # Example

# Verify
date
# Should show correct time for your location
```

### 5.7 Configure Automatic Security Updates (Optional but Recommended)

```bash
# Install unattended-upgrades
sudo apt install -y unattended-upgrades

# Enable automatic updates
sudo dpkg-reconfigure -plow unattended-upgrades

# Select "Yes" when prompted

# This will automatically install security patches
# System will reboot automatically if kernel is updated (usually overnight)
```

---

## Part 6: Install Docker

### 6.1 Remove Old Docker Versions (if any)

```bash
# Remove old versions
sudo apt remove -y docker docker-engine docker.io containerd runc

# It's OK if this says "package not found" - that means nothing to remove
```

### 6.2 Install Docker Engine

**We'll use Docker's official installation script:**

```bash
# Download Docker installation script
curl -fsSL https://get.docker.com -o get-docker.sh

# Inspect it (optional, but good practice)
cat get-docker.sh | less
# Press 'q' to quit

# Run the installation script
sudo sh get-docker.sh

# This takes 2-3 minutes
# You'll see lots of output ending with:
# "To run Docker as a non-privileged user, consider setting up the Docker daemon..."
```

### 6.3 Configure Docker for Non-Root User

**Allow your user to run Docker without `sudo`:**

```bash
# Add your user to docker group
sudo usermod -aG docker $USER

# Activate the changes (logout and login)
# You can either:
# A) Log out and back in via SSH
exit
# Then reconnect: ssh deer@192.168.1.200

# OR B) Use newgrp (works immediately)
newgrp docker

# To verify you can now run Docker without sudo:
docker ps
```

### 6.4 Verify Docker Installation

```bash
# Check Docker version
docker --version
# Should show: Docker version 24.x.x, build xxxxx

# Check Docker Compose (built into Docker now)
docker compose version
# Should show: Docker Compose version v2.x.x

# Run test container (this confirms Docker is working!)
docker run hello-world

# You should see:
# "Hello from Docker!"
# "This message shows that your installation appears to be working correctly."
```

**✓ Docker is now installed and working!**

### 6.5 Configure Docker to Start on Boot

```bash
# Enable Docker service
sudo systemctl enable docker

# Enable containerd (Docker's runtime)
sudo systemctl enable containerd

# Verify services are running
sudo systemctl status docker
# Should show: "active (running)"

# Press 'q' to quit the status view
```

### 6.6 Optimize Docker for ML Workloads (Optional)

```bash
# Edit Docker daemon configuration
sudo nano /etc/docker/daemon.json
```

**Add this configuration:**

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  },
  "default-address-pools": [
    {
      "base": "172.17.0.0/16",
      "size": 24
    }
  ],
  "storage-driver": "overlay2"
}
```

**Save and exit** (Ctrl+O, Enter, Ctrl+X)

**Restart Docker:**

```bash
# Restart Docker daemon
sudo systemctl restart docker

# Verify it restarted successfully
sudo systemctl status docker
```

---

## Part 7: Deploy Deer Deterrent System

### 7.1 Clone the Repository

```bash
# Navigate to home directory
cd ~

# Clone the repository
git clone https://github.com/rndpig/deer-deterrent.git

# Navigate into it
cd deer-deterrent

# Check that files are there
ls -la
# You should see: backend/ frontend/ src/ configs/ docker-compose.yml etc.
```

### 7.2 Create Dell-Specific Directory Structure

```bash
# Create deployment directories
mkdir -p dell-deployment
mkdir -p dell-deployment/logs
mkdir -p dell-deployment/data
mkdir -p dell-deployment/data/snapshots
mkdir -p dell-deployment/data/database
mkdir -p dell-deployment/models
mkdir -p dell-deployment/ring-mqtt
mkdir -p dell-deployment/mosquitto/{config,data,log}

# Set proper permissions
chmod -R 755 dell-deployment
```

### 7.3 Review the All-in-One Docker Compose

The repository now includes `docker-compose.dell.yml` with all services configured!

```bash
# View the Docker Compose configuration
cat docker-compose.dell.yml
```

**This includes:**
- 🎨 **Frontend** (Vite/React dashboard)
- ⚙️ **Backend** (FastAPI API server)
- 🤖 **ML Detector** (YOLOv8 inference service)
- 📹 **Ring MQTT** (Ring camera integration)
- 🚰 **Coordinator** (Sprinkler activation logic)
- 🗄️ **Database** (PostgreSQL)
- 📡 **MQTT Broker** (Mosquitto)

### 7.4 Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env.dell

# Edit it with your settings
nano .env.dell
```

**Important variables to set:**

```bash
# ===========================================
# Dell Deployment Configuration
# ===========================================

# Network Configuration
DELL_SERVER_IP=192.168.7.200
TIMEZONE=America/New_York

# Ring Camera Configuration
RING_USERNAME=your-email@example.com
RING_PASSWORD=your-ring-password
RING_2FA_METHOD=sms  # or 'email', 'authenticator'

# Rainbird Controller Configuration
RAINBIRD_IP=192.168.7.XXX  # We'll find this later
RAINBIRD_PASSWORD=your-rainbird-password
RAINBIRD_ZONE=1
RAINBIRD_DURATION_SECONDS=30

# ML Model Configuration
YOLO_MODEL_PATH=/app/models/deer_detector.pt
CONFIDENCE_THRESHOLD=0.75
COOLDOWN_SECONDS=300

# Database Configuration
POSTGRES_DB=deer_deterrent
POSTGRES_USER=deeruser
POSTGRES_PASSWORD=ChangeThisToASecurePassword123!

# Frontend Configuration
VITE_API_URL=http://192.168.7.200:8000

# Security
JWT_SECRET_KEY=ChangeThisToARandomSecretKey789!

# Logging
LOG_LEVEL=INFO
```

**Save and exit** (Ctrl+O, Enter, Ctrl+X)

### 7.5 Download Pre-Trained YOLO Model

We need a deer detection model. Options:

**Option A: Use a pre-trained wildlife model (Quick Start)**

```bash
# Download YOLOv8 model trained on COCO dataset
cd dell-deployment/models
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt

# This is a general object detection model
# We'll fine-tune it later with your deer data
```

**Option B: Train custom model (Do later after system is running)**

We'll use the training notebook once you collect deer images.

### 7.6 Configure Mosquitto MQTT

```bash
# Create Mosquitto config
nano dell-deployment/mosquitto/config/mosquitto.conf
```

**Add:**

```conf
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
log_dest stdout
log_type all
```

**Save and exit**

### 7.7 Deploy All Services

**This is the moment of truth! Let's start everything:**

```bash
# Navigate to deployment directory
cd ~/deer-deterrent

# Start all services in background
docker compose -f docker-compose.dell.yml --env-file .env.dell up -d

# This will:
# 1. Download all Docker images (takes 5-10 minutes first time)
# 2. Build custom containers
# 3. Start all services

# Watch the logs as services start
docker compose -f docker-compose.dell.yml logs -f

# You should see:
# - Database: "database system is ready to accept connections"
# - Backend: "Uvicorn running on http://0.0.0.0:8000"
# - Frontend: "VITE vX.X.X  ready in XXX ms"
# - ML Detector: "Loaded YOLOv8 model successfully"
# - Ring MQTT: "Successfully connected to Ring"
# - Coordinator: "Coordinator service started"

# Press Ctrl+C to exit logs (containers keep running)
```

---

## Part 8: Configure Services

### 8.1 Verify All Services Are Running

```bash
# Check service status
docker compose -f docker-compose.dell.yml ps

# All services should show "Up" status:
# NAME                 STATUS
# deer-frontend        Up
# deer-backend         Up
# deer-ml-detector     Up
# deer-coordinator     Up
# deer-db              Up
# deer-ring-mqtt       Up
# deer-mosquitto       Up
```

### 8.2 Access the Frontend Dashboard

**On your Windows PC, open browser:**

```
http://192.168.7.200:3000
```

**You should see the Deer Deterrent Dashboard!**

### 8.3 Test Backend API

```bash
# From the Dell via SSH
curl http://localhost:8000/health

# Should return:
# {"status":"healthy","version":"1.0.0"}

# Test from Windows PC browser:
# http://192.168.7.200:8000/docs
# This shows the interactive API documentation (Swagger UI)
```

### 8.4 Configure Ring Authentication

Ring requires 2FA, so we need to get a token manually:

```bash
# Check ring-mqtt logs for authentication instructions
docker compose -f docker-compose.dell.yml logs ring-mqtt

# You'll see a URL to authenticate
# Open it in browser on Windows PC
# Complete Ring login + 2FA
# Copy the token provided
```

**Update the token in .env.dell:**

```bash
nano .env.dell

# Find RING_REFRESH_TOKEN and add your token:
RING_REFRESH_TOKEN=your-token-from-ring-auth

# Save and restart ring-mqtt
docker compose -f docker-compose.dell.yml restart ring-mqtt
```

**Verify Ring connection:**

```bash
# Check logs again
docker compose -f docker-compose.dell.yml logs ring-mqtt | tail -20

# Should see: "Successfully connected to Ring API"
# Should see: "Found X cameras"
```

### 8.5 Configure Rainbird Controller

**First, find your Rainbird controller on the network:**

```bash
# Scan network for Rainbird (takes 1-2 minutes)
sudo nmap -sn 192.168.7.0/24 | grep -B 2 -i rain

# Or check your router's connected devices list
```

**Test Rainbird connection:**

```bash
# Once you have the IP, test it
curl http://192.168.7.XXX

# Or ping it
ping 192.168.7.XXX -c 4
```

**Update .env.dell with Rainbird IP:**

```bash
nano .env.dell

# Update:
RAINBIRD_IP=192.168.7.XXX  # Your actual Rainbird IP

# Save and restart coordinator
docker compose -f docker-compose.dell.yml restart coordinator
```

### 8.6 Test ML Detection

**Upload a test image:**

```bash
# Download a test deer image
cd ~/deer-deterrent/dell-deployment/data
wget https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/White-tailed_deer.jpg/1200px-White-tailed_deer.jpg -O test_deer.jpg

# Test the ML detector
curl -X POST http://localhost:8001/detect \
  -F "file=@test_deer.jpg" \
  | jq .

# Should return detection results with confidence scores
```

---

## Part 9: Testing and Validation

### 9.1 Component Health Checks

**Run these commands to verify each component:**

```bash
# Frontend
curl http://localhost:3000
# Should return HTML

# Backend
curl http://localhost:8000/health
# Should return: {"status":"healthy"}

# ML Detector
curl http://localhost:8001/health
# Should return: {"status":"ready","model":"yolov8n"}

# Database
docker compose -f docker-compose.dell.yml exec db psql -U deeruser -d deer_deterrent -c "SELECT 1;"
# Should return: " 1 "

# MQTT Broker
docker compose -f docker-compose.dell.yml exec mosquitto mosquitto_sub -t test -C 1 &
docker compose -f docker-compose.dell.yml exec mosquitto mosquitto_pub -t test -m "hello"
# Should show: hello
```

### 9.2 End-to-End Test

**Simulate a deer detection event:**

```bash
# Send a test webhook
curl -X POST http://localhost:5000/webhook/test \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "test-camera",
    "timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%SZ)'",
    "snapshot_url": "http://localhost:8001/test-images/deer.jpg"
  }'

# Check coordinator logs
docker compose -f docker-compose.dell.yml logs coordinator | tail -30

# You should see:
# - Downloaded snapshot
# - ML detection ran
# - Deer detected with confidence X.XX
# - Sprinkler activation attempted
```

### 9.3 View Logs

**Useful log commands:**

```bash
# All services
docker compose -f docker-compose.dell.yml logs -f

# Specific service
docker compose -f docker-compose.dell.yml logs -f coordinator

# Last 50 lines
docker compose -f docker-compose.dell.yml logs --tail=50 coordinator

# Follow logs with timestamps
docker compose -f docker-compose.dell.yml logs -f -t

# Search logs for errors
docker compose -f docker-compose.dell.yml logs | grep -i error
```

---

## Part 10: Maintenance and Troubleshooting

### 10.1 Daily Operations

**Check system status:**

```bash
# Quick status check
docker compose -f docker-compose.dell.yml ps

# Resource usage
docker stats

# Disk usage
df -h
du -sh ~/deer-deterrent/dell-deployment/*
```

**Restart services:**

```bash
# Restart all
docker compose -f docker-compose.dell.yml restart

# Restart specific service
docker compose -f docker-compose.dell.yml restart coordinator

# Stop all
docker compose -f docker-compose.dell.yml stop

# Start all
docker compose -f docker-compose.dell.yml start
```

### 10.2 Updates and Upgrades

**Update the application:**

```bash
# Pull latest code
cd ~/deer-deterrent
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.dell.yml up -d --build

# View logs to verify
docker compose -f docker-compose.dell.yml logs -f
```

**Update Ubuntu system:**

```bash
# Update packages (do this monthly)
sudo apt update
sudo apt upgrade -y
sudo apt autoremove -y

# Check for reboot requirement
if [ -f /var/run/reboot-required ]; then
  echo "Reboot required!"
  cat /var/run/reboot-required.pkgs
fi

# Reboot if needed
sudo reboot
```

### 10.3 Backup and Recovery

**Backup important data:**

```bash
# Create backup script
nano ~/backup.sh
```

**Add:**

```bash
#!/bin/bash
BACKUP_DIR=~/backups
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# Backup database
docker compose -f ~/deer-deterrent/docker-compose.dell.yml exec -T db \
  pg_dump -U deeruser deer_deterrent > $BACKUP_DIR/db_$DATE.sql

# Backup configuration
cp ~/deer-deterrent/.env.dell $BACKUP_DIR/env_$DATE.backup

# Backup snapshots and logs
tar -czf $BACKUP_DIR/data_$DATE.tar.gz ~/deer-deterrent/dell-deployment/data

# Keep only last 7 days of backups
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR"
```

**Save and make executable:**

```bash
chmod +x ~/backup.sh

# Run manually
~/backup.sh

# Or add to cron (daily at 2 AM)
crontab -e
# Add: 0 2 * * * /home/deer/backup.sh
```

### 10.4 Common Issues and Solutions

**Issue: Container won't start**

```bash
# Check logs for specific container
docker compose -f docker-compose.dell.yml logs <service-name>

# Check Docker daemon
sudo systemctl status docker

# Restart Docker
sudo systemctl restart docker
```

**Issue: Out of disk space**

```bash
# Check disk usage
df -h

# Clean Docker unused resources
docker system prune -a

# Clean old logs
sudo journalctl --vacuum-time=7d
```

**Issue: Ring connection lost**

```bash
# Refresh Ring token (it expires every ~6 months)
docker compose -f docker-compose.dell.yml logs ring-mqtt

# Follow the re-authentication link in logs
# Update .env.dell with new token
# Restart ring-mqtt
docker compose -f docker-compose.dell.yml restart ring-mqtt
```

**Issue: ML detection too slow**

```bash
# Check if GPU is being used (if available)
docker compose -f docker-compose.dell.yml exec ml-detector python -c "import torch; print(torch.cuda.is_available())"

# Reduce model size (use yolov8n instead of yolov8m)
# Update YOLO_MODEL_PATH in .env.dell
```

**Issue: Can't access from Windows PC**

```bash
# Check firewall on Dell
sudo ufw status

# If firewall is active, allow ports
sudo ufw allow 3000/tcp  # Frontend
sudo ufw allow 8000/tcp  # Backend
sudo ufw allow 5000/tcp  # Coordinator

# Or test from Windows PC:
# Can you ping the server?
ping 192.168.7.200

# Check if services are listening on Dell
sudo netstat -tulpn | grep -E ':(3000|8000|5000)'
```

### 10.5 Monitoring and Alerts

**Install monitoring tools:**

```bash
# Install htop for system monitoring
sudo apt install -y htop

# Run it
htop

# Press F10 to exit
```

**Monitor Docker resource usage:**

```bash
# Real-time container stats
docker stats

# Shows CPU, Memory, Network I/O for each container
```

**Set up email alerts (optional):**

```bash
# Install mail utilities
sudo apt install -y mailutils

# Test email
echo "Test from deer-server" | mail -s "Test Alert" your-email@example.com

# Create alert script for critical events
nano ~/alert.sh
```

---

## Part 11: Next Steps

### 11.1 Production Checklist

Before going live with deer detection:

- ✅ All services running and healthy
- ✅ Ring camera connected and receiving events
- ✅ Rainbird controller responding to commands
- ✅ ML detector accurately identifying deer (>75% confidence)
- ✅ Cooldown period configured (prevent sprinkler spam)
- ✅ Test detection → sprinkler activation pipeline
- ✅ Set up daily backups
- ✅ Configure time-based rules (e.g., only active at night)
- ✅ Monitor logs for first few days

### 11.2 Training Custom Model

Once you have deer images:

1. Collect 100+ images of deer in your yard
2. Annotate them using the training notebook
3. Upload to Google Drive
4. Run training on Google Colab (free GPU!)
5. Download trained model
6. Copy to `dell-deployment/models/`
7. Update `YOLO_MODEL_PATH` in `.env.dell`
8. Restart ML detector

### 11.3 Advanced Features

**Add time-based activation:**

```bash
# Edit coordinator to only run during certain hours
# Example: Only active from 6 PM to 6 AM
```

**Add zone mapping:**

```bash
# Configure different sprinkler zones for different cameras
# Edit configs/zones.yaml
```

**Add notification system:**

```bash
# Send email/SMS when deer detected
# Integrate with Twilio or SendGrid
```

**Add detection history dashboard:**

```bash
# Already included in frontend!
# View all detections, confidence scores, timestamps
# Filter by date range
```

---

## Appendix A: Quick Reference Commands

### Service Management

```bash
# Start all services
docker compose -f docker-compose.dell.yml up -d

# Stop all services
docker compose -f docker-compose.dell.yml down

# Restart specific service
docker compose -f docker-compose.dell.yml restart <service-name>

# View logs
docker compose -f docker-compose.dell.yml logs -f

# Check status
docker compose -f docker-compose.dell.yml ps
```

### System Maintenance

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Check disk space
df -h

# Clean Docker
docker system prune -a

# Reboot
sudo reboot
```

### Debugging

```bash
# Check service health
curl http://localhost:8000/health  # Backend
curl http://localhost:8001/health  # ML Detector
curl http://localhost:5000/health  # Coordinator

# Enter container shell
docker compose -f docker-compose.dell.yml exec <service-name> bash

# View container logs
docker compose -f docker-compose.dell.yml logs <service-name>

# Check network connectivity
ping google.com
nslookup google.com
```

---

## Appendix B: Network Ports Reference

| Port | Service | Purpose |
|------|---------|---------|
| 3000 | Frontend | Web dashboard UI |
| 8000 | Backend | API server |
| 8001 | ML Detector | YOLO inference service |
| 5000 | Coordinator | Webhook receiver & sprinkler control |
| 5432 | PostgreSQL | Database |
| 1883 | MQTT | Ring camera events |
| 55123 | Ring MQTT UI | Ring configuration web interface |

---

## Appendix C: Troubleshooting Decision Tree

```
Problem: System not detecting deer
├─ Is Ring sending events?
│  ├─ No → Check ring-mqtt logs, verify Ring credentials
│  └─ Yes → Continue
├─ Is ML detector running?
│  ├─ No → Check ml-detector logs, restart service
│  └─ Yes → Continue
├─ Is confidence threshold too high?
│  ├─ Yes → Lower CONFIDENCE_THRESHOLD in .env.dell
│  └─ No → Continue
└─ Is model trained on deer?
   ├─ No → Train custom model or use wildlife-specific model
   └─ Yes → Check logs for detection results

Problem: Sprinkler not activating
├─ Is Rainbird controller reachable?
│  ├─ No → Check network, verify RAINBIRD_IP
│  └─ Yes → Continue
├─ Is cooldown period active?
│  ├─ Yes → Wait or reduce COOLDOWN_SECONDS
│  └─ No → Continue
├─ Check coordinator logs for errors
└─ Test Rainbird API manually with curl

Problem: Can't access dashboard
├─ Is frontend container running?
│  ├─ No → docker compose up -d frontend
│  └─ Yes → Continue
├─ Can you ping 192.168.1.200?
│  ├─ No → Check network connection
│  └─ Yes → Continue
├─ Is port 3000 open?
│  ├─ No → Check firewall: sudo ufw allow 3000/tcp
│  └─ Yes → Check browser console for errors
```

---

## Support

For issues specific to this deployment:
- Check logs: `docker compose logs`
- GitHub Issues: https://github.com/rndpig/deer-deterrent/issues
- Review documentation: `README.md`, `DEPLOYMENT.md`

For general Ubuntu/Docker help:
- Ubuntu documentation: https://help.ubuntu.com
- Docker documentation: https://docs.docker.com
- Ask Ubuntu: https://askubuntu.com

---

**You're all set! Your Dell OptiPlex is now a powerful deer deterrent server.** 🦌 💦

The system will automatically:
1. Monitor Ring cameras for motion
2. Detect deer using ML
3. Activate sprinklers when deer appear
4. Log all events to the dashboard
5. Prevent false positives with cooldown
6. Run 24/7 reliably

**Happy deer deterring!**
