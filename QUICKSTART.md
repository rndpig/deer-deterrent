# Dell OptiPlex Quick Start Guide
## Get Your Deer Deterrent System Running in 1-2 Hours

This is your fast-track guide to getting the deer deterrent system running on your Dell OptiPlex 9020.

---

## 🎯 Overview

**What you're building:** A complete AI-powered deer detection and deterrent system running on a single Dell PC.

**Time required:**
- Ubuntu installation: 30-45 minutes
- System configuration: 30 minutes
- Deer deterrent deployment: 15-20 minutes
- Testing and fine-tuning: 30 minutes

**Total: ~2 hours** (mostly hands-off waiting for installations)

---

## 📚 Three Documents, Three Purposes

1. **THIS FILE** (`QUICKSTART_DELL.md`) - Quick overview to get started NOW
2. **`DELL_DEPLOYMENT.md`** - Comprehensive step-by-step instructions with explanations
3. **`DELL_CHECKLIST.md`** - Track your progress, don't forget any steps

**Recommended approach:**
1. Read this quick start to understand the process
2. Follow `DELL_DEPLOYMENT.md` for detailed steps
3. Use `DELL_CHECKLIST.md` to check off completed tasks

---

## ⚡ Super Quick Start (For the Impatient)

If you're familiar with Linux and Docker:

```bash
# 1. Install Ubuntu Server 24.04 LTS on Dell (BIOS: UEFI, disable Secure Boot)
# 2. Set static IP: 192.168.1.200

# 3. Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# 4. Clone and deploy
git clone https://github.com/rndpig/deer-deterrent.git
cd deer-deterrent
cp .env.example .env.dell

# 5. Edit .env.dell with your settings
nano .env.dell
# - Set DELL_SERVER_IP, RING credentials, RAINBIRD_IP, passwords

# 6. Create directories
mkdir -p dell-deployment/{logs,data/{snapshots,database},models,ring-mqtt,mosquitto/{config,data,log}}

# 7. Download YOLO model
cd dell-deployment/models
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
cd ../..

# 8. Create Mosquitto config
cat > dell-deployment/mosquitto/config/mosquitto.conf << 'EOF'
listener 1883
allow_anonymous true
persistence true
persistence_location /mosquitto/data/
log_dest file /mosquitto/log/mosquitto.log
log_dest stdout
EOF

# 9. Deploy!
docker compose --env-file .env.dell up -d

# 10. Watch logs
docker compose logs -f

# 11. Access dashboard
# Open browser: http://192.168.1.200:3000
```

**Done!** Now skip to the [Testing](#testing) section below.

---

## 📖 Detailed Quick Start

### Step 1: Prepare Installation Media (On Windows PC)

1. **Download Ubuntu Server:**
   - Go to: https://ubuntu.com/download/server
   - Download: Ubuntu Server 24.04 LTS (ubuntu-24.04-live-server-amd64.iso)
   - Size: ~2.6 GB

2. **Download Rufus:**
   - Go to: https://rufus.ie/
   - Download: Rufus 4.x Portable

3. **Create bootable USB:**
   - Insert 8GB+ USB drive (will be erased!)
   - Run Rufus
   - Select USB drive
   - Click "SELECT" → choose Ubuntu ISO
   - Partition scheme: GPT
   - Target system: UEFI (non CSM)
   - Click "START"
   - Wait 5-10 minutes

✅ **Checkpoint:** You now have a bootable Ubuntu USB drive.

---

### Step 2: Install Ubuntu (On Dell OptiPlex)

1. **Connect peripherals to Dell:**
   - Monitor, keyboard, mouse
   - Ethernet cable to router
   - USB drive (front port)
   - Power cable

2. **Enter BIOS and configure:**
   - Power on, press F2 repeatedly
   - Boot → Boot Sequence → Set to UEFI
   - Boot → Boot List → USB first
   - Secure Boot → Disable
   - Virtualization Support → Enable VT-x and VT-d
   - Save and Exit (F10)

3. **Install Ubuntu:**
   - Boot from USB
   - Select "Try or Install Ubuntu Server"
   - Language: English
   - Keyboard: English (US)
   - Installation type: Ubuntu Server
   - Network: Auto-configured (note the IP!)
   - Storage: Use entire disk + LVM (will erase SSD!)
   - Profile setup:
     - Name: Your name
     - Server: `deer-server`
     - Username: `deer`
     - Password: [choose strong password]
   - **IMPORTANT:** Enable OpenSSH server ✓
   - Skip server snaps
   - Wait 10-15 minutes for installation
   - Remove USB when prompted, reboot

4. **First login:**
   - Login: `deer` + your password
   - Update system:
     ```bash
     sudo apt update
     sudo apt upgrade -y
     sudo apt install -y curl wget git nano htop net-tools
     ```

✅ **Checkpoint:** Ubuntu is installed and updated.

---

### Step 3: Configure Network

1. **Find current IP:**
   ```bash
   ip addr show
   # Note the IP address (e.g., 192.168.1.150)
   ```

2. **Set static IP via Netplan:**
   ```bash
   sudo nano /etc/netplan/50-cloud-init.yaml
   ```
   
   Change to (customize for your network):
   ```yaml
   network:
       ethernets:
           enp0s25:
               dhcp4: no
               addresses:
                   - 192.168.1.200/24
               routes:
                   - to: default
                     via: 192.168.1.1
               nameservers:
                   addresses:
                       - 8.8.8.8
                       - 8.8.4.4
       version: 2
   ```
   
   Apply:
   ```bash
   sudo netplan try
   # Press Enter if network still works
   sudo netplan apply
   ```

3. **Test SSH from Windows:**
   ```powershell
   ssh deer@192.168.1.200
   ```

4. **Set timezone:**
   ```bash
   sudo timedatectl set-timezone America/New_York
   ```

✅ **Checkpoint:** Dell has static IP, accessible via SSH. You can now disconnect monitor/keyboard!

---

### Step 4: Install Docker

From now on, do everything via SSH from your Windows PC:

```bash
# Download and run Docker installer
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group
sudo usermod -aG docker $USER

# Refresh group membership (or logout/login)
newgrp docker

# Verify Docker
docker --version
docker compose version
docker run hello-world

# Enable Docker at boot
sudo systemctl enable docker
sudo systemctl enable containerd
```

✅ **Checkpoint:** Docker is installed and working.

---

### Step 5: Deploy Deer Deterrent System

1. **Clone repository:**
   ```bash
   cd ~
   git clone https://github.com/rndpig/deer-deterrent.git
   cd deer-deterrent
   ```

2. **Create directory structure:**
   ```bash
   mkdir -p dell-deployment/logs
   mkdir -p dell-deployment/data/snapshots
   mkdir -p dell-deployment/data/database
   mkdir -p dell-deployment/models
   mkdir -p dell-deployment/ring-mqtt
   mkdir -p dell-deployment/mosquitto/config
   mkdir -p dell-deployment/mosquitto/data
   mkdir -p dell-deployment/mosquitto/log
   ```

3. **Download YOLO model:**
   ```bash
   cd dell-deployment/models
   wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
   cd ../..
   ```

4. **Configure Mosquitto:**
   ```bash
   cat > dell-deployment/mosquitto/config/mosquitto.conf << 'EOF'
   listener 1883
   allow_anonymous true
   persistence true
   persistence_location /mosquitto/data/
   log_dest file /mosquitto/log/mosquitto.log
   log_dest stdout
   log_type all
   EOF
   ```

5. **Create environment file:**
   ```bash
   cp .env.example .env.dell
   nano .env.dell
   ```
   
   **Minimum required changes:**
   ```bash
   DELL_SERVER_IP=192.168.1.200
   POSTGRES_PASSWORD=YourStrongPasswordHere123!
   JWT_SECRET_KEY=YourRandomSecretKeyHere789!
   RING_USERNAME=your-email@example.com
   RING_PASSWORD=your-ring-password
   RING_2FA_METHOD=email
   RAINBIRD_IP=192.168.1.XXX
CONFIDENCE_THRESHOLD=0.75
COOLDOWN_SECONDS=300
ENABLE_IRRIGATION=false
```   Save with: Ctrl+O, Enter, Ctrl+X

6. **Deploy all services:**
   ```bash
   docker compose --env-file .env.dell up -d
   ```
   
   First time takes 5-10 minutes to download all images.

7. **Watch logs:**
   ```bash
   docker compose logs -f
   ```
   
   Wait until you see:
   - "database system is ready to accept connections"
   - "Uvicorn running on http://0.0.0.0:8000"
   - "VITE ready"
   - "Loaded YOLOv8 model successfully"
   - "Connected to MQTT broker"
   
   Press Ctrl+C to exit (containers keep running)

✅ **Checkpoint:** All services are running!

---

### Step 6: Configure Ring Camera

1. **Open Ring MQTT web UI:**
   - Browser: `http://192.168.1.200:55123`

2. **Authenticate with Ring:**
   - Click "Get Ring Token"
   - Log into your Ring account
   - Complete 2FA
   - Copy the refresh token

3. **Update configuration:**
   ```bash
   nano .env.dell
   # Add: RING_REFRESH_TOKEN=<paste token here>
   # Save and exit
   ```

4. **Restart Ring MQTT:**
   ```bash
   docker compose restart ring-mqtt
   ```

5. **Verify connection:**
   ```bash
   docker compose logs ring-mqtt | tail -20
   # Should see: "Successfully connected to Ring API"
   # Should see: "Found X cameras"
   ```

✅ **Checkpoint:** Ring cameras connected!

---

### Step 7: Configure Rainbird

1. **Find Rainbird controller:**
   ```bash
   sudo nmap -sn 192.168.1.0/24 | grep -B 2 -i rain
   # Or check your router's connected devices list
   ```

2. **Update configuration:**
   ```bash
   nano .env.dell
   # Update: RAINBIRD_IP=192.168.1.XXX
   # Update: RAINBIRD_ZONE=1  (or whatever zone you want)
   # Save and exit
   ```

3. **Restart coordinator:**
   ```bash
   docker compose restart coordinator
   ```

✅ **Checkpoint:** Rainbird configured!

---

### Step 8: Testing

1. **Make management script executable:**
   ```bash
   chmod +x manage.sh
   ```

2. **Check system health:**
   ```bash
   ./manage.sh health
   ```
   
   All services should return "healthy" status.

3. **Run system test:**
   ```bash
   ./manage.sh test
   ```
   
   This:
   - Downloads a test deer image
   - Sends it to ML detector
   - Triggers test webhook
   - You should see detection results

4. **Test with real camera:**
   - Trigger motion on your Ring camera (walk in front of it)
   - Watch coordinator logs:
     ```bash
     ./manage.sh logs coordinator
     ```
   - Should see:
     - "Motion detected on camera..."
     - "Downloaded snapshot"
     - "ML detection: X objects, deer=true/false"
          - "Deer detected (or not detected - based on scene)"
     - "Irrigation activation attempted" (but won't actually activate yet)

5. **View dashboard:**
   - Open browser: `http://192.168.1.200:3000`
   - You should see the deer deterrent dashboard
   - Check detection history

✅ **Checkpoint:** System is detecting motion and processing images!

---

### Step 9: Go Live

1. **Monitor for a few days in dry-run mode:**
   - Keep `ENABLE_IRRIGATION=false`
   - Check logs daily: `./manage.sh logs coordinator`
   - Review detection accuracy
   - Adjust `CONFIDENCE_THRESHOLD` if needed

2. **When ready, enable irrigation:**
   ```bash
   nano .env.dell
   # Change: ENABLE_IRRIGATION=true
   # Save and exit
   
   docker compose restart coordinator
   ```

3. **Test live activation:**
   - Trigger camera motion with a real deer (or simulate)
   - Verify irrigation activates
   - Check cooldown works (second event doesn't activate immediately)

4. **Set up automated backups:**
   ```bash
   crontab -e
   # Add this line (runs backup daily at 2 AM):
   0 2 * * * /home/deer/deer-deterrent/manage.sh backup
   ```

✅ **Checkpoint:** System is LIVE! 🎉

---

## 🎛️ Daily Operations

### Check system status:
```bash
./manage.sh status    # Service status
./manage.sh health    # Health checks
./manage.sh stats     # Resource usage
```

### View logs:
```bash
./manage.sh logs              # All services
./manage.sh logs coordinator  # Specific service
```

### Restart services:
```bash
./manage.sh restart           # All services
./manage.sh restart coordinator  # Specific service
```

### Monitor live:
```bash
./manage.sh monitor  # Live dashboard (refreshes every 5s)
```

### Update system:
```bash
./manage.sh update   # Pull latest code and rebuild
```

### Backup data:
```bash
./manage.sh backup   # Manual backup
```

### Get help:
```bash
./manage.sh help     # Show all commands
```

---

## 🔧 Configuration Tuning

### Too many false positives?
```bash
nano .env.dell
# Increase: CONFIDENCE_THRESHOLD=0.80
docker compose restart coordinator
```

### Missing deer detections?
```bash
nano .env.dell
# Decrease: CONFIDENCE_THRESHOLD=0.65
docker compose restart coordinator
```

### Irrigation activating too often?
```bash
nano .env.dell
# Increase: COOLDOWN_SECONDS=600  (10 minutes)
docker compose restart coordinator
```

### Only want activation at night?
```bash
nano .env.dell
# Set: ACTIVE_HOURS_START=18  (6 PM)
# Set: ACTIVE_HOURS_END=6     (6 AM)
docker compose restart coordinator
```

---

## 🐛 Troubleshooting

### Service won't start?
```bash
docker compose logs <service-name>
# Check logs for errors
```

### Can't access dashboard?
```bash
# Check if frontend is running
docker compose ps frontend

# Check firewall
sudo ufw status
sudo ufw allow 3000/tcp

# Try from Dell itself
curl http://localhost:3000
```

### Ring not connecting?
```bash
# Token may have expired (every 6 months)
# Go to: http://192.168.1.200:55123
# Re-authenticate and update RING_REFRESH_TOKEN
```

### ML detection slow?
- Normal on CPU: 2-5 seconds
- If >10 seconds, check `docker stats` for resource usage
- Consider using smaller model: `yolov8n.pt` instead of `yolov8m.pt`

### Out of disk space?
```bash
./manage.sh clean  # Remove unused Docker resources
df -h              # Check disk usage
```

---

## 📊 Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| Dashboard | http://192.168.1.200:3000 | Main UI |
| Backend API Docs | http://192.168.1.200:8000/docs | API documentation |
| ML Detector Docs | http://192.168.1.200:8001/docs | ML API documentation |
| Ring MQTT UI | http://192.168.1.200:55123 | Ring configuration |
| SSH | ssh deer@192.168.1.200 | System access |

---

## 🎓 Learning Resources

- **Docker basics:** https://docs.docker.com/get-started/
- **Docker Compose:** https://docs.docker.com/compose/
- **Ubuntu Server:** https://ubuntu.com/server/docs
- **YOLOv8:** https://docs.ultralytics.com/

---

## 🚨 Emergency Commands

### Stop everything:
```bash
docker compose down
```

### Restart everything:
```bash
docker compose restart
```

### View all containers:
```bash
docker ps -a
```

### Check system resources:
```bash
htop  # Press F10 to exit
```

### Reboot Dell:
```bash
sudo reboot
```

---

## ✅ Success Checklist

Your system is ready when:
- [ ] All services show "Up" in `./manage.sh status`
- [ ] Dashboard loads at http://192.168.1.200:3000
- [ ] Ring cameras connected and sending events
- [ ] ML detector successfully processes images
- [ ] Test detection works (deer identified correctly)
- [ ] Irrigation activates when deer detected (if enabled)
- [ ] Events appear in dashboard history
- [ ] System stable for 24+ hours
- [ ] Backups running successfully

---

## 🎉 You're Done!

Your Dell OptiPlex is now a powerful, always-on deer deterrent system!

**Next steps:**
1. Monitor for a week to ensure stability
2. Fine-tune confidence threshold based on results
3. Train custom model with your own deer images (optional)
4. Add notification integrations (email/SMS) if desired

**For detailed documentation:**
- Full instructions: `DELL_DEPLOYMENT.md`
- Progress tracking: `DELL_CHECKLIST.md`
- Project overview: `README.md`

**Need help?**
- Check logs: `./manage.sh logs`
- Run diagnostics: `./manage.sh health`
- See troubleshooting section in `DELL_DEPLOYMENT.md`

---

**Happy deer deterring!** 🦌💦

*Remember: Start with `ENABLE_IRRIGATION=false` to test thoroughly before going live!*
