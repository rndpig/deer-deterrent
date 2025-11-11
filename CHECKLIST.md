# Dell OptiPlex Deployment Checklist
## Deer Deterrent System - Quick Reference

Use this checklist to track your progress through the Dell deployment process.

---

## 📋 Pre-Installation Checklist

### Hardware Preparation
- [ ] Dell OptiPlex 9020 available and powered off
- [ ] Monitor + HDMI/DisplayPort cable connected
- [ ] USB keyboard + mouse connected
- [ ] Ethernet cable connected to router
- [ ] 8GB+ USB flash drive available (will be erased!)
- [ ] Verified all Dell specs (i7-4790, 16GB RAM, 256GB SSD)

### Software Downloads (on Windows PC)
- [ ] Ubuntu Server 24.04 LTS ISO downloaded
- [ ] Rufus portable downloaded
- [ ] Bootable USB drive created with Rufus

### Network Information Collected
- [ ] Router admin credentials ready
- [ ] Chosen static IP for Dell (e.g., 192.168.1.200)
- [ ] Router IP address known (usually 192.168.1.1)
- [ ] WiFi credentials ready (optional backup)

### Account Credentials Ready
- [ ] Ring account username/password
- [ ] Ring 2FA method known
- [ ] Rainbird controller password (if applicable)
- [ ] Strong passwords generated for database and JWT

---

## 💻 Ubuntu Installation Checklist

### BIOS Configuration
- [ ] Entered BIOS (F2 during boot)
- [ ] Set boot order: USB first, then SSD
- [ ] Set boot mode to UEFI
- [ ] Disabled Secure Boot
- [ ] Enabled Intel Virtualization (VT-x)
- [ ] Enabled VT for Direct I/O (VT-d)
- [ ] Saved and exited BIOS

### Ubuntu Installation
- [ ] Booted from USB successfully
- [ ] Selected "Try or Install Ubuntu Server"
- [ ] Chose English language
- [ ] Skipped installer update
- [ ] Configured keyboard (English US)
- [ ] Selected Ubuntu Server (not minimized)
- [ ] Network auto-configured via DHCP
- [ ] Noted initial IP address: `___.___.___.___ `
- [ ] Skipped proxy configuration
- [ ] Accepted default Ubuntu mirror
- [ ] Selected "Use entire disk" with LVM
- [ ] Did NOT enable encryption
- [ ] Reviewed partition layout (looks good)
- [ ] Confirmed destructive action (SSD will be erased!)
- [ ] Created user account:
  - Username: `deer` (or custom: `__________`)
  - Password: Set and written down securely
  - Server name: `deer-server`
- [ ] Skipped Ubuntu Pro
- [ ] **ENABLED OpenSSH server** ✓ Important!
- [ ] Skipped server snaps
- [ ] Installation completed (10-15 min wait)
- [ ] Removed USB drive when prompted
- [ ] System rebooted successfully

### First Login
- [ ] Logged in at console: `deer` + password
- [ ] Ran `sudo apt update`
- [ ] Ran `sudo apt upgrade -y` (5-10 min wait)
- [ ] Installed essential tools: `sudo apt install -y curl wget git nano htop net-tools`
- [ ] Found IP address with `ip addr show`
- [ ] Current IP: `___.___.___.___ `

---

## 🌐 Network Configuration Checklist

### Static IP Configuration
- [ ] Chose static IP: `192.168.1.200` (or custom: `___.___.___.___ `)
- [ ] Confirmed router gateway IP: `192.168.1.1` (or custom: `___.___.___.___ `)

**Option A: Netplan (on Dell)**
- [ ] Edited `/etc/netplan/50-cloud-init.yaml`
- [ ] Set `dhcp4: no`
- [ ] Added static IP address
- [ ] Added gateway (router IP)
- [ ] Added DNS servers (8.8.8.8, 8.8.4.4)
- [ ] Ran `sudo netplan try` (tested for 120 sec)
- [ ] Ran `sudo netplan apply`
- [ ] Verified with `ip addr show enp0s25`

**Option B: Router DHCP Reservation (alternative)**
- [ ] Logged into router admin panel
- [ ] Found DHCP reservation settings
- [ ] Added reservation with Dell's MAC address
- [ ] IP reserved: `___.___.___.___ `
- [ ] Saved router settings
- [ ] Rebooted Dell

### SSH Access
- [ ] Tested SSH from Windows: `ssh deer@192.168.1.200`
- [ ] Accepted SSH fingerprint (typed `yes`)
- [ ] Successfully logged in via SSH
- [ ] Can now disconnect monitor/keyboard from Dell ✓

### System Configuration
- [ ] Set timezone: `sudo timedatectl set-timezone America/New_York`
- [ ] Verified time: `date` (shows correct time)
- [ ] Enabled automatic security updates: `sudo apt install -y unattended-upgrades`
- [ ] Configured: `sudo dpkg-reconfigure -plow unattended-upgrades`

---

## 🐳 Docker Installation Checklist

### Docker Setup
- [ ] Downloaded Docker install script: `curl -fsSL https://get.docker.com -o get-docker.sh`
- [ ] Ran install script: `sudo sh get-docker.sh`
- [ ] Added user to docker group: `sudo usermod -aG docker $USER`
- [ ] Logged out and back in (or ran `newgrp docker`)
- [ ] Verified Docker: `docker --version` (shows v24.x.x)
- [ ] Verified Docker Compose: `docker compose version` (shows v2.x.x)
- [ ] Tested Docker: `docker run hello-world` (successful!)

### Docker Configuration
- [ ] Enabled Docker service: `sudo systemctl enable docker`
- [ ] Enabled containerd: `sudo systemctl enable containerd`
- [ ] Verified status: `sudo systemctl status docker` (active)
- [ ] Created `/etc/docker/daemon.json` with optimizations
- [ ] Restarted Docker: `sudo systemctl restart docker`

---

## 🦌 Deer Deterrent Deployment Checklist

### Repository Setup
- [ ] Cloned repo: `git clone https://github.com/rndpig/deer-deterrent.git`
- [ ] Changed to directory: `cd deer-deterrent`
- [ ] Verified files present: `ls -la` (see README, docker-compose.yml, etc.)

### Directory Structure
- [ ] Created deployment directories:
  ```bash
  mkdir -p dell-deployment/{logs,data/snapshots,data/database,models,ring-mqtt,mosquitto/{config,data,log}}
  ```
- [ ] Set permissions: `chmod -R 755 dell-deployment`

### YOLO Model
- [ ] Downloaded YOLOv8 nano model:
  ```bash
  cd dell-deployment/models
  wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.pt
  ```
- [ ] Verified file: `ls -lh yolov8n.pt` (file exists)

### Mosquitto Configuration
- [ ] Created `/dell-deployment/mosquitto/config/mosquitto.conf`
- [ ] Added listener and permissions
- [ ] Saved configuration

### Environment Configuration
- [ ] Copied template: `cp .env.example .env.dell`
- [ ] Edited: `nano .env.dell`
- [ ] Updated `DELL_SERVER_IP=192.168.1.200`
- [ ] Updated `POSTGRES_PASSWORD` (strong password!)
- [ ] Updated `JWT_SECRET_KEY` (random string!)
- [ ] Updated `RING_USERNAME` (your Ring email)
- [ ] Updated `RING_PASSWORD` (your Ring password)
- [ ] Updated `RING_2FA_METHOD` (email/sms/authenticator)
- [ ] Updated `RAINBIRD_IP` (will find later: `___.___.___.___ `)
- [ ] Set `CONFIDENCE_THRESHOLD=0.75`
- [ ] Set `COOLDOWN_SECONDS=300`
- [ ] Set `ENABLE_SPRINKLER=false` (testing mode!)
- [ ] Set `ACTIVE_HOURS_START=0`
- [ ] Set `ACTIVE_HOURS_END=24`
- [ ] Saved `.env.dell` file

---

## 🚀 Service Deployment Checklist

### First Deployment
- [ ] Started services: `docker compose --env-file .env.dell up -d`
- [ ] Waited for image downloads (5-10 minutes first time)
- [ ] Watched logs: `docker compose logs -f`
- [ ] Saw "database system is ready to accept connections"
- [ ] Saw "Uvicorn running on http://0.0.0.0:8000" (backend)
- [ ] Saw "VITE ready" (frontend)
- [ ] Saw "Loaded YOLOv8 model successfully" (ML detector)
- [ ] Saw "Connected to MQTT broker" (coordinator)
- [ ] Pressed Ctrl+C to exit logs (containers keep running)

### Service Verification
- [ ] Checked status: `docker compose ps`
- [ ] All services show "Up" status
- [ ] Verified frontend: Open browser to `http://192.168.1.200:3000`
- [ ] Saw dashboard load successfully
- [ ] Verified backend: `curl http://localhost:8000/health` (returns JSON)
- [ ] Verified ML detector: `curl http://localhost:8001/health` (returns JSON)
- [ ] Verified coordinator: `curl http://localhost:5000/health` (returns JSON)
- [ ] Verified database: Container running and healthy

---

## 🎯 Ring Camera Integration Checklist

### Ring MQTT Setup
- [ ] Opened Ring MQTT UI in browser: `http://192.168.1.200:55123`
- [ ] Clicked "Get Ring Token"
- [ ] Logged into Ring account
- [ ] Completed 2FA verification
- [ ] Copied refresh token provided
- [ ] Updated `.env.dell` with `RING_REFRESH_TOKEN=<token>`
- [ ] Restarted ring-mqtt: `docker compose restart ring-mqtt`
- [ ] Checked logs: `docker compose logs ring-mqtt`
- [ ] Saw "Successfully connected to Ring API"
- [ ] Saw "Found X cameras" in logs
- [ ] Ring cameras discovered: _____ cameras

### Ring Event Testing
- [ ] Manually triggered motion on Ring camera
- [ ] Checked coordinator logs: `docker compose logs coordinator`
- [ ] Saw "Motion detected on camera..." message
- [ ] Verified MQTT message received

---

## 💧 Rainbird Integration Checklist

### Find Rainbird Controller
- [ ] Scanned network: `sudo nmap -sn 192.168.1.0/24 | grep -B 2 -i rain`
- [ ] Or checked router's connected devices list
- [ ] Found Rainbird IP: `___.___.___.___ `
- [ ] Pinged to verify: `ping <rainbird-ip> -c 4` (successful)
- [ ] Updated `.env.dell` with `RAINBIRD_IP=<ip>`

### Rainbird API Discovery
- [ ] Identified Rainbird model: ____________
- [ ] Tested web interface: `http://<rainbird-ip>` (if available)
- [ ] Documented API endpoints needed
- [ ] Implemented API calls in coordinator (or placeholder for now)

### Manual Rainbird Test
- [ ] Used Rainbird mobile app to activate zone 1
- [ ] Verified sprinklers activate correctly
- [ ] Noted which zone covers deer-prone area: Zone _____
- [ ] Updated `.env.dell` with correct `RAINBIRD_ZONE`

---

## 🧪 System Testing Checklist

### Component Tests
- [ ] Made manage script executable: `chmod +x manage.sh`
- [ ] Ran health check: `./manage.sh health`
- [ ] All services returned healthy status
- [ ] Ran system test: `./manage.sh test`
- [ ] ML detector processed test image successfully
- [ ] Coordinator received test webhook
- [ ] Checked logs for test event processing

### End-to-End Test (Dry Run)
- [ ] Verified `ENABLE_SPRINKLER=false` in `.env.dell`
- [ ] Triggered Ring camera motion event
- [ ] Checked coordinator logs for:
  - [ ] Motion event received
  - [ ] Snapshot downloaded
  - [ ] ML detection ran
  - [ ] Deer detected (or not detected - based on scene)
  - [ ] Sprinkler activation logged (but not actually activated)
- [ ] Checked backend logs for event storage
- [ ] Viewed detection in dashboard

### Detection Accuracy Testing
- [ ] Collected 10+ test images with deer
- [ ] Uploaded to ML detector manually
- [ ] Calculated detection rate: _____ / 10 detected
- [ ] Checked false positive rate on non-deer images
- [ ] Adjusted `CONFIDENCE_THRESHOLD` if needed: New value: _____

---

## ✅ Production Readiness Checklist

### Final Configuration
- [ ] `ENABLE_SPRINKLER=true` set in `.env.dell`
- [ ] Confidence threshold optimized: `CONFIDENCE_THRESHOLD=_____`
- [ ] Cooldown period set appropriately: `COOLDOWN_SECONDS=_____`
- [ ] Active hours configured: `ACTIVE_HOURS_START=_____ to ACTIVE_HOURS_END=_____`
- [ ] Correct Rainbird zone: `RAINBIRD_ZONE=_____`
- [ ] Sprinkler duration set: `RAINBIRD_DURATION_SECONDS=_____`
- [ ] Restarted all services: `./manage.sh restart`

### Live Testing
- [ ] Monitored system with: `./manage.sh monitor`
- [ ] Waited for real Ring camera motion event
- [ ] Verified complete flow:
  - [ ] Motion detected
  - [ ] Snapshot processed
  - [ ] Deer detected
  - [ ] **SPRINKLER ACTIVATED** ✓
  - [ ] Event logged to database
  - [ ] Visible in dashboard
- [ ] Verified cooldown working (second event within cooldown not activated)

### Monitoring & Maintenance
- [ ] Set up daily backup cron job: `crontab -e` → `0 2 * * * ~/deer-deterrent/manage.sh backup`
- [ ] Verified backups working: `./manage.sh backup`
- [ ] Checked backup location: `ls ~/backups/`
- [ ] Documented how to check logs: `./manage.sh logs coordinator`
- [ ] Documented how to restart: `./manage.sh restart`
- [ ] Created monitoring routine (check weekly)

---

## 📊 Post-Deployment Monitoring

### Week 1 Checklist
- [ ] Day 1: Check logs daily for errors
- [ ] Day 2: Verify detection accuracy
- [ ] Day 3: Confirm sprinkler activations working
- [ ] Day 4: Check disk space: `df -h`
- [ ] Day 5: Review false positive rate
- [ ] Day 6: Adjust confidence threshold if needed
- [ ] Day 7: Run backup: `./manage.sh backup`

### Ongoing Maintenance
- [ ] Weekly: Check system health: `./manage.sh health`
- [ ] Weekly: Review detection logs
- [ ] Monthly: Update system: `sudo apt update && sudo apt upgrade -y`
- [ ] Monthly: Update containers: `./manage.sh update`
- [ ] Quarterly: Review and clean old snapshots
- [ ] Quarterly: Test backup restoration

---

## 🐛 Troubleshooting Reference

### Quick Diagnostics
```bash
# Check all services
./manage.sh status

# View all logs
./manage.sh logs

# View specific service logs
./manage.sh logs coordinator
./manage.sh logs ml-detector
./manage.sh logs ring-mqtt

# Check resource usage
./manage.sh stats

# Restart services
./manage.sh restart

# Health check
./manage.sh health
```

### Common Issues
- **Ring not connecting**: Check `RING_REFRESH_TOKEN`, may need to re-authenticate
- **ML detector slow**: Normal on CPU, 2-5 seconds expected
- **Sprinkler not activating**: Check `ENABLE_SPRINKLER=true` and `RAINBIRD_IP`
- **Dashboard not loading**: Check `DELL_SERVER_IP` in `.env.dell` matches actual IP
- **Out of disk space**: Run `./manage.sh clean` to free up space

---

## 📝 Notes Section

Use this space for your specific notes:

**Dell Server Info:**
- Static IP: ___.___.___.___ 
- SSH: `ssh deer@___.___.___.___ `

**Ring Cameras:**
- Camera 1: ____________ (ID: ____________)
- Camera 2: ____________ (ID: ____________)

**Rainbird Controller:**
- Model: ____________
- IP: ___.___.___.___ 
- Zone 1: ____________
- Zone 2: ____________

**Passwords (store securely elsewhere!):**
- Ubuntu user: ✓ Stored in password manager
- Postgres: ✓ Stored in password manager
- JWT secret: ✓ Stored in password manager

**Important Dates:**
- Installation date: ___________
- Ring token refresh needed by: ___________ (6 months from install)
- Last backup: ___________
- Last system update: ___________

---

## 🎉 Success Criteria

Your system is fully operational when:
- ✅ All services show "Up" status
- ✅ Frontend dashboard accessible and loading
- ✅ Ring cameras connected and sending events
- ✅ ML detector successfully identifying deer
- ✅ Sprinklers activating when deer detected
- ✅ Events logged to database and visible in dashboard
- ✅ Cooldown period preventing sprinkler spam
- ✅ System running stable for 7+ days
- ✅ Backups completing successfully

**Congratulations! Your deer deterrent system is live!** 🦌💦

---

*For detailed instructions, see: `DELL_DEPLOYMENT.md`*
*For quick commands, run: `./manage.sh help`*
