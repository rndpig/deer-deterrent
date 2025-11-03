# QNAP Container Station Setup - Detailed Guide

This is a comprehensive, step-by-step guide for deploying the Deer Deterrent backend to your QNAP NAS. Every command and screenshot location is included.

## Part 1: QNAP Prerequisites and Setup

### What is Container Station?

Container Station is QNAP's Docker management interface. It provides:
- Docker container management via GUI
- Docker Compose support
- Resource monitoring
- Auto-restart capabilities
- Built-in image registry

### 1.1 Install Container Station (If Not Already Installed)

**Important:** Container Station availability depends on your QNAP model and QTS version.

#### Check Your QNAP Model Compatibility

Container Station is available on:
- All x86-based QNAP models (Intel/AMD processors)
- ARM-based models with 4GB+ RAM
- QTS 4.2.0 or later

**Not available on:**
- Very old QNAP models (pre-2015)
- ARM models with less than 2GB RAM

#### Method 1: Find Container Station in App Center

1. **Open QNAP Admin Interface**
   - Navigate to `http://YOUR-QNAP-IP:8080` in browser
   - Or just `http://YOUR-QNAP-IP` if using default HTTP port
   - Login with admin credentials

2. **Access App Center**
   - Click the **App Center** icon (looks like a grid of squares)
   - Or find it in the main menu

3. **Search for Container Station**
   - In the search bar, type: `Container Station`
   - **Alternative names to try:**
     - `Container`
     - `Docker`
     - Look under **Utilities** or **Developer Tools** categories

4. **If Container Station appears:**
   - Click **Install** button
   - Wait 2-3 minutes for installation
   - Click **Open** when installation completes

#### Method 2: Manual Installation via QPKG

**If Container Station is not in App Center, install manually:**

1. **Determine Your QNAP Architecture**
   - SSH into QNAP: `ssh admin@YOUR-QNAP-IP`
   - Run: `uname -m`
   - Output will be something like:
     - `x86_64` - Intel/AMD 64-bit (most common)
     - `i686` - Intel/AMD 32-bit
     - `armv7l` - ARM 32-bit
     - `aarch64` - ARM 64-bit

2. **Check QTS Version**
   - In QNAP web interface: **Control Panel** → **System** → **System Status**
   - Or via SSH: `cat /etc/version`
   - Note the version (e.g., "QTS 5.0.1")

3. **Download Container Station QPKG**
   
   Visit QNAP's official download page:
   - Go to: https://www.qnap.com/en/software/container-station
   - Or search Google for: "QNAP Container Station download"
   - Select your model or architecture
   - Download the `.qpkg` file

4. **Install QPKG Manually**
   - QNAP Web Interface → **App Center**
   - Click the **gear icon** (⚙️) in top-right
   - Select **Install Manually**
   - Click **Browse** and select the downloaded `.qpkg` file
   - Click **OK** to install
   - Wait 2-5 minutes for installation

#### Method 3: Alternative - Use Docker Directly via SSH

**If Container Station installation fails or isn't available:**

You can use Docker directly from the command line without Container Station.

1. **Install Docker via QPKG**
   
   Some QNAP models have Docker as a separate package:
   - App Center → Search for "Docker"
   - Or manually install Docker QPKG

2. **Or Install Docker via opkg (package manager)**
   
   ```bash
   # SSH into QNAP
   ssh admin@YOUR-QNAP-IP
   
   # Check if opkg is available
   opkg --version
   
   # If opkg exists, install Docker
   opkg update
   opkg install docker docker-compose
   
   # Start Docker service
   /etc/init.d/docker start
   
   # Enable auto-start
   update-rc.d docker defaults
   ```

3. **Or Use Entware (Third-Party Package Manager)**
   
   ```bash
   # SSH into QNAP
   ssh admin@YOUR-QNAP-IP
   
   # Install Entware (if not already installed)
   # Visit: https://github.com/Entware/Entware/wiki/Install-on-QNAP-NAS
   
   # Download Entware installer for your architecture
   # For x86_64:
   wget http://bin.entware.net/x64-k3.2/installer/entware_install.sh
   sh entware_install.sh
   
   # Install Docker via Entware
   opkg install docker docker-compose
   ```

#### Method 4: Check Model-Specific Limitations

**Some QNAP models have specific requirements:**

1. **Check QNAP Community Forums**
   - Search: "Container Station [YOUR QNAP MODEL]"
   - Example: "Container Station TS-251+"

2. **Contact QNAP Support**
   - They can confirm if your model supports Container Station
   - May provide direct download link

3. **Check for Firmware Updates**
   - Old firmware may not support Container Station
   - Update QTS: **Control Panel** → **System** → **Firmware Update**

#### What to Do After This Section:

- ✅ **If Container Station installs successfully**: Continue to section 1.2
- ⚠️ **If using Docker directly (Method 3)**: Skip Container Station GUI steps, use command line only
- ❌ **If nothing works**: Let me know your QNAP model and QTS version, I'll provide alternative deployment instructions

5. **Initial Container Station Setup** (Skip if using Docker directly)
   - Accept terms of service
   - Choose storage location (usually default is fine)
   - Enable **Docker Hub** registry access
   - Click **Apply**

### 1.2 Enable SSH Access on QNAP

1. **Open QNAP Control Panel**
   - Click **Main Menu** → **Control Panel**

2. **Navigate to Network & File Services**
   - Click **Telnet / SSH** in left sidebar

3. **Enable SSH**
   - Check **Allow SSH connection**
   - Port: `22` (default)
   - Click **Apply**

4. **Test SSH Connection from Windows**
   ```powershell
   # Replace with your QNAP's IP address
   ssh admin@192.168.1.XXX
   
   # Type 'yes' to accept fingerprint
   # Enter your admin password
   
   # You should see QNAP command prompt
   # Type 'exit' to disconnect
   ```

### 1.3 Check QNAP System Resources

**Via Web Interface:**
1. Main Menu → **Resource Monitor**
2. Check available resources:
   - **RAM**: Need at least 4GB free (8GB+ recommended)
   - **CPU**: Any modern QNAP CPU works
   - **Storage**: Need ~10GB free for Docker images + model

**Via SSH:**
```bash
# Connect to QNAP
ssh admin@YOUR-QNAP-IP

# Check RAM
free -h

# Check disk space
df -h

# Check CPU
cat /proc/cpuinfo | grep "model name" | head -1
```

## Part 2: Preparing Your Development Machine

### 2.1 Verify Project Files Are Ready

```powershell
# Navigate to project directory
cd "C:\Users\rndpi\Documents\Coding Projects\deer-deterrent"

# Verify key files exist
ls backend/main.py
ls backend/requirements.txt
ls backend/Dockerfile
ls models/production/best.pt
ls src/inference/detector.py

# Check git status (should be clean)
git status
```

### 2.2 Optional: Test Backend Locally First (Skip if Dependencies Won't Install)

If you want to verify the backend code before deploying:

```powershell
# Activate virtual environment
& ".venv/Scripts/Activate.ps1"

# Try to run backend
python backend/main.py

# If it fails due to missing packages (torch, opencv, etc), that's expected
# We'll install them in Docker on QNAP instead
```

### 2.3 Find Your QNAP's IP Address

**Method 1 - QNAP Finder (Windows App):**
1. Download QNAP Finder from QNAP website
2. Run it, it will auto-discover your QNAP
3. Note the IP address shown

**Method 2 - Check Router:**
1. Log into your router admin panel
2. Look for connected devices / DHCP leases
3. Find device named "QNAP" or similar
4. Note the IP address

**Method 3 - QNAP Display (if NAS has LCD):**
- Some QNAP models show IP on front panel display

### 2.4 Create Transfer Script (Optional but Recommended)

Create a PowerShell script to make file transfers easier:

```powershell
# Create deploy script
New-Item -Path ".\deploy-to-qnap.ps1" -ItemType File -Force

# Edit the file and add:
```

**deploy-to-qnap.ps1:**
```powershell
# Configuration
$QNAP_IP = "192.168.1.XXX"  # Replace with your QNAP IP
$QNAP_USER = "admin"
$PROJECT_PATH = "C:\Users\rndpi\Documents\Coding Projects\deer-deterrent"
$QNAP_PATH = "/share/Container/deer-deterrent"

Write-Host "Deploying Deer Deterrent to QNAP..." -ForegroundColor Green

# Navigate to project
cd $PROJECT_PATH

# Create tar of backend
Write-Host "`nPackaging backend..." -ForegroundColor Yellow
tar -czf backend.tar.gz backend/

# Create tar of source
Write-Host "Packaging source code..." -ForegroundColor Yellow
tar -czf src.tar.gz src/

# Create tar of models
Write-Host "Packaging models..." -ForegroundColor Yellow
tar -czf models.tar.gz models/

# Transfer files
Write-Host "`nTransferring files to QNAP..." -ForegroundColor Yellow
scp backend.tar.gz "${QNAP_USER}@${QNAP_IP}:${QNAP_PATH}/"
scp src.tar.gz "${QNAP_USER}@${QNAP_IP}:${QNAP_PATH}/"
scp models.tar.gz "${QNAP_USER}@${QNAP_IP}:${QNAP_PATH}/"

# Clean up local tar files
Write-Host "`nCleaning up..." -ForegroundColor Yellow
Remove-Item backend.tar.gz, src.tar.gz, models.tar.gz

Write-Host "`nTransfer complete!" -ForegroundColor Green
Write-Host "Next: SSH into QNAP and extract files" -ForegroundColor Cyan
```

## Part 3: Setting Up Directories on QNAP

### 3.1 Connect to QNAP via SSH

```powershell
ssh admin@192.168.1.XXX
```

### 3.2 Create Directory Structure

```bash
# Navigate to Container storage
cd /share/Container

# Create main application directory
mkdir -p deer-deterrent
cd deer-deterrent

# Create subdirectories
mkdir -p backend
mkdir -p src
mkdir -p models/production
mkdir -p logs
mkdir -p data/detections
mkdir -p data/history

# Verify structure
tree -L 2
# Or if tree not available:
ls -R

# Set permissions
chmod -R 755 .
```

### 3.3 Understanding QNAP File Paths

QNAP has a unique directory structure:

- `/share/Container/` - Container Station's default storage location
- `/share/CACHEDEV1_DATA/` - Main data partition (alternative location)
- `/etc/` - System configuration (don't use for app data)
- `/tmp/` - Temporary storage (cleared on reboot)

**Use `/share/Container/deer-deterrent` for this project.**

## Part 4: Transferring Files to QNAP

### Option A: Using SCP (Recommended)

**From your Windows PowerShell:**

```powershell
# Navigate to project
cd "C:\Users\rndpi\Documents\Coding Projects\deer-deterrent"

# Transfer backend directory
scp -r backend admin@192.168.1.XXX:/share/Container/deer-deterrent/

# Transfer source code
scp -r src admin@192.168.1.XXX:/share/Container/deer-deterrent/

# Transfer model file
scp models/production/best.pt admin@192.168.1.XXX:/share/Container/deer-deterrent/models/production/

# Verify transfer (SSH into QNAP)
ssh admin@192.168.1.XXX
cd /share/Container/deer-deterrent
ls -lh backend/
ls -lh src/
ls -lh models/production/
```

**Expected file sizes to verify:**
- `backend/main.py` - ~10-15 KB
- `backend/requirements.txt` - ~200 bytes
- `models/production/best.pt` - ~6 MB
- `src/inference/detector.py` - ~3-5 KB

### Option B: Using QNAP File Station (GUI Method)

**If SCP fails or you prefer GUI:**

1. **Open QNAP File Station**
   - Browser: `http://YOUR-QNAP-IP:8080`
   - Click **File Station** icon

2. **Navigate to Container Directory**
   - Click on folder tree: `Container` → `deer-deterrent`
   - Or type in address bar: `/Container/deer-deterrent`

3. **Upload Backend Folder**
   - Click **Upload** button (↑ icon)
   - Select **Upload Folder**
   - Browse to: `C:\Users\rndpi\Documents\Coding Projects\deer-deterrent\backend`
   - Click **Upload**
   - Wait for completion (shows progress)

4. **Upload Source Folder**
   - Repeat above for `src` folder

5. **Upload Model File**
   - Navigate into `models/production/` folder in File Station
   - Click **Upload** → **Upload File**
   - Select `best.pt` from your local `models/production/` folder
   - Upload (may take 1-2 minutes for ~6MB file)

6. **Verify in File Station**
   - Check all files are present
   - Verify file sizes match originals

### Option C: Using Git Clone (Advanced)

**If you want to use git directly on QNAP:**

```bash
# SSH into QNAP
ssh admin@192.168.1.XXX

# Install git if not available
# (Check if git exists)
git --version

# If git not found, install via QNAP Package Center or:
opkg install git

# Clone repository
cd /share/Container
git clone https://github.com/rndpig/deer-deterrent.git
cd deer-deterrent

# Pull latest changes anytime with:
git pull
```

**Pros:** Easy updates with `git pull`  
**Cons:** Entire repo downloaded including frontend (not needed on QNAP)

## Part 5: Creating Docker Compose Configuration

### 5.1 Understanding Docker Compose

Docker Compose is a tool for defining multi-container applications using YAML. Our setup uses a single container but Compose makes management easier.

**What the compose file does:**
- Defines the Python base image
- Maps local directories into the container
- Exposes port 8000
- Installs dependencies on first run
- Auto-restarts if crashes

### 5.2 Create docker-compose.yml

**SSH into QNAP:**
```bash
ssh admin@192.168.1.XXX
cd /share/Container/deer-deterrent
```

**Create the compose file:**
```bash
cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  deer-api:
    image: python:3.11-slim
    container_name: deer-deterrent-api
    restart: unless-stopped
    working_dir: /app
    
    volumes:
      - ./backend:/app/backend
      - ./src:/app/src
      - ./models:/app/models
      - ./logs:/app/logs
      - ./data:/app/data
    
    ports:
      - "8000:8000"
    
    environment:
      - PYTHONUNBUFFERED=1
      - TZ=America/New_York
      - PYTHONPATH=/app
    
    command: >
      bash -c "
        echo '=== Starting Deer Deterrent API ===' &&
        echo 'Installing system dependencies...' &&
        apt-get update -qq &&
        apt-get install -y -qq libgl1-mesa-glx libglib2.0-0 &&
        echo 'Installing Python packages...' &&
        pip install --no-cache-dir -q -r /app/backend/requirements.txt &&
        echo 'Starting FastAPI server...' &&
        cd /app &&
        uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
      "
    
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/api/stats')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 90s

networks:
  default:
    name: deer-deterrent-network
EOF
```

**Verify the file was created:**
```bash
cat docker-compose.yml
```

### 5.3 Understanding the Configuration

Let's break down key sections:

**Image:**
```yaml
image: python:3.11-slim
```
- Uses official Python 3.11 image
- "slim" variant is smaller (150MB vs 1GB for full image)
- Still includes everything we need

**Volumes (Bind Mounts):**
```yaml
volumes:
  - ./backend:/app/backend
```
- Maps local `./backend` folder into container at `/app/backend`
- Changes to local files are immediately reflected in container
- Perfect for development - no rebuild needed for code changes

**Ports:**
```yaml
ports:
  - "8000:8000"
```
- Maps container port 8000 to host port 8000
- Format: `HOST:CONTAINER`
- Allows access via `http://QNAP-IP:8000`

**Environment Variables:**
```yaml
environment:
  - PYTHONUNBUFFERED=1  # Shows print() output immediately
  - TZ=America/New_York  # Set timezone
  - PYTHONPATH=/app      # Python module search path
```

**Command Explanation:**
The `command` section runs on container start:
1. Updates apt package list
2. Installs OpenCV dependencies (libgl1-mesa-glx, libglib2.0-0)
3. Installs Python packages from requirements.txt
4. Starts uvicorn server

**Health Check:**
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "..."]
  interval: 30s
  start_period: 90s
```
- Every 30 seconds, checks if `/api/stats` responds
- Waits 90 seconds before first check (allows time for startup)
- Container marked "unhealthy" if 3 checks fail

**Restart Policy:**
```yaml
restart: unless-stopped
```
- Auto-restart if container crashes
- Restart on QNAP reboot
- Only stops if manually stopped with `docker-compose down`

## Part 6: Deploying the Container

### 6.1 First Deployment

**SSH into QNAP:**
```bash
ssh admin@192.168.1.XXX
cd /share/Container/deer-deterrent
```

**Start the container:**
```bash
# Deploy in detached mode (background)
docker-compose up -d

# You'll see:
# Creating network "deer-deterrent-network" with the default driver
# Pulling deer-api (python:3.11-slim)...
# Creating deer-deterrent-api ... done
```

**This first run will take 10-15 minutes** because:
1. Downloads Python 3.11 image (~150 MB)
2. Downloads PyTorch (~800 MB)
3. Downloads Ultralytics + dependencies (~400 MB)
4. Downloads OpenCV + dependencies (~200 MB)

### 6.2 Monitor Installation Progress

**Watch real-time logs:**
```bash
docker-compose logs -f deer-api
```

You'll see output like:
```
deer-api | === Starting Deer Deterrent API ===
deer-api | Installing system dependencies...
deer-api | Installing Python packages...
deer-api | Collecting torch==2.5.0
deer-api |   Downloading torch-2.5.0-cp311-cp311-manylinux...
deer-api | Collecting ultralytics==8.3.223
deer-api | ...
deer-api | Successfully installed torch-2.5.0 ultralytics-8.3.223 ...
deer-api | Starting FastAPI server...
deer-api | INFO:     Started server process [1]
deer-api | INFO:     Waiting for application startup.
deer-api | ✓ Detector initialized   <-- Look for this!
deer-api | INFO:     Application startup complete.
deer-api | INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Key things to look for:**
- ✅ "Successfully installed torch..."
- ✅ "Successfully installed ultralytics..."
- ✅ "✓ Detector initialized" (means ML model loaded)
- ✅ "Application startup complete"
- ✅ "Uvicorn running on http://0.0.0.0:8000"

**Press `Ctrl+C` to stop watching logs** (container keeps running in background)

### 6.3 Troubleshooting Installation Issues

**If installation hangs or fails:**

```bash
# Stop container
docker-compose down

# View full logs
docker-compose logs deer-api

# Common issues:

# 1. Out of memory
free -h  # Check available RAM
# Solution: Close other containers or apps

# 2. Disk space full
df -h  # Check disk space
# Solution: Clear old Docker images: docker image prune

# 3. Network timeout
# Solution: Retry - Docker caches downloads

# Start again
docker-compose up -d
docker-compose logs -f deer-api
```

### 6.4 Verify Container is Running

```bash
# Check container status
docker-compose ps

# Expected output:
#           Name                         State           Ports
# ----------------------------------------------------------------
# deer-deterrent-api   Up 2 minutes   0.0.0.0:8000->8000/tcp
```

**Status should be "Up"** - if it shows "Restarting" or "Exited", check logs:
```bash
docker-compose logs deer-api
```

### 6.5 Test the API Locally on QNAP

```bash
# Test from QNAP command line
curl http://localhost:8000/api/stats

# Expected response:
# {"total_detections":0,"total_deer":0,"sprinklers_activated":0,"last_detection":null}

# Test settings endpoint
curl http://localhost:8000/api/settings

# Expected: JSON with settings

# Test health endpoint
curl http://localhost:8000/health
```

If all three return JSON (not errors), **the backend is working!**

## Part 7: Container Management

### 7.1 Essential Docker Compose Commands

**From QNAP SSH in `/share/Container/deer-deterrent`:**

```bash
# View running containers
docker-compose ps

# Start containers
docker-compose up -d

# Stop containers (preserves data)
docker-compose stop

# Stop and remove containers (preserves volumes/data)
docker-compose down

# View logs (last 100 lines)
docker-compose logs --tail=100 deer-api

# Follow logs in real-time
docker-compose logs -f deer-api

# Restart container (after code changes)
docker-compose restart

# Restart and rebuild (if docker-compose.yml changed)
docker-compose up -d --force-recreate

# Execute command inside running container
docker-compose exec deer-api bash
# Now you're inside container - type 'exit' to leave

# Check container resource usage
docker stats deer-deterrent-api
```

### 7.2 Viewing Logs via Container Station GUI

**Alternative to command line:**

1. Open Container Station in QNAP web interface
2. Click **Containers** in left sidebar
3. Find **deer-deterrent-api** in list
4. Click the container name
5. Click **Logs** tab
6. View real-time logs
7. Can download logs as file

### 7.3 Managing Container Lifecycle

**Auto-start on QNAP boot:**
- Already configured with `restart: unless-stopped`
- Container automatically starts when QNAP powers on
- No manual intervention needed

**Manually stopping container:**
```bash
docker-compose stop
```

**Manually starting stopped container:**
```bash
docker-compose start
```

**Complete removal (keeps data):**
```bash
docker-compose down
# Data in /share/Container/deer-deterrent persists
# Re-run 'docker-compose up -d' to recreate
```

### 7.4 Resource Monitoring

**Check resource usage:**
```bash
# Container stats (updates every second)
docker stats deer-deterrent-api

# Press Ctrl+C to exit

# QNAP system resources
top

# Disk usage
df -h /share/Container
```

**Expected resource usage:**
- **RAM**: 2-4 GB (when idle with model loaded)
- **CPU**: 1-5% idle, 50-100% during detection
- **Disk**: ~3-4 GB for container + dependencies

### 7.5 Updating Code

**After making changes on Windows and pushing to GitHub:**

**Option 1 - Manual file copy:**
```powershell
# On Windows
cd "C:\Users\rndpi\Documents\Coding Projects\deer-deterrent"
scp -r backend admin@QNAP-IP:/share/Container/deer-deterrent/

# On QNAP
ssh admin@QNAP-IP
cd /share/Container/deer-deterrent
docker-compose restart
```

**Option 2 - Git pull (if using git on QNAP):**
```bash
# SSH into QNAP
cd /share/Container/deer-deterrent
git pull
docker-compose restart
```

**Option 3 - Full redeploy:**
```bash
# If you changed docker-compose.yml or requirements.txt
docker-compose down
docker-compose up -d --force-recreate
```

## Part 8: Troubleshooting Common Issues

### Issue 1: Container Won't Start

**Symptoms:** Status shows "Exited" or "Restarting"

**Diagnosis:**
```bash
docker-compose logs deer-api
```

**Common causes:**

**A) Port 8000 already in use:**
```bash
# Check what's using port 8000
netstat -tulpn | grep 8000

# If something else is using it, either:
# 1. Stop that service, or
# 2. Change port in docker-compose.yml:
#    ports:
#      - "8001:8000"  # Use external port 8001 instead
```

**B) Permission errors:**
```bash
# Fix permissions
cd /share/Container/deer-deterrent
chmod -R 755 .
docker-compose restart
```

**C) Missing files:**
```bash
# Verify all files present
ls -R /share/Container/deer-deterrent
# Should see backend/, src/, models/production/best.pt
```

### Issue 2: Out of Memory

**Symptoms:** Container crashes, logs show "Killed"

**Solution:**
```bash
# Check available memory
free -h

# If less than 4GB available:
# 1. Stop other containers:
docker ps  # List running containers
docker stop OTHER-CONTAINER-NAME

# 2. Or restart QNAP to clear memory
# 3. Or upgrade QNAP RAM
```

### Issue 3: Slow Detection Performance

**Symptoms:** API responds slowly, high CPU usage

**Explanation:** YOLO runs on CPU (no GPU) which is slower

**Solutions:**
- Increase confidence threshold (fewer detections)
- Add cooldown periods between detections
- Consider QNAP with GPU support (rare/expensive)
- This is expected behavior for CPU-based ML

### Issue 4: Model Not Found

**Symptoms:** Logs show "⚠ Detector initialization failed"

**Diagnosis:**
```bash
# Check if model file exists
docker-compose exec deer-api ls -lh /app/models/production/

# Should show best.pt (~6MB)
```

**Solution:**
```bash
# If missing, copy model file
scp models/production/best.pt admin@QNAP-IP:/share/Container/deer-deterrent/models/production/

# Restart container
docker-compose restart
```

### Issue 5: Can't Access from Other Devices

**Symptoms:** Works on QNAP but not from Windows PC

**Diagnosis:**
```bash
# On QNAP, test locally
curl http://localhost:8000/api/stats  # Works

# From Windows PC
curl http://QNAP-IP:8000/api/stats  # Fails
```

**Common causes:**

**A) QNAP firewall blocking:**
1. QNAP Web Interface → **Control Panel** → **Security**
2. Click **Firewall**
3. Add rule: Allow TCP port 8000 from all IPs (or specific IP range)
4. Test again

**B) Container not bound to external interface:**
- Check docker-compose.yml has `0.0.0.0:8000` not `127.0.0.1:8000`
- Our config is correct: `0.0.0.0:8000:8000`

**C) Port mapping issue:**
```bash
# Verify port mapping
docker port deer-deterrent-api
# Should show: 8000/tcp -> 0.0.0.0:8000
```

## Part 9: Performance Optimization

### 9.1 Optimize Docker Image Size (Optional)

**Current setup downloads packages on every fresh start. To speed up restarts:**

Create a custom Dockerfile:

```bash
cd /share/Container/deer-deterrent
cat > Dockerfile << 'EOF'
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y libgl1-mesa-glx libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY backend /app/backend
COPY src /app/src
COPY models /app/models

# Set Python path
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Run uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
EOF
```

**Update docker-compose.yml to use custom image:**
```yaml
version: '3.8'

services:
  deer-api:
    build: .  # Build from local Dockerfile
    container_name: deer-deterrent-api
    restart: unless-stopped
    
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    
    ports:
      - "8000:8000"
    
    environment:
      - PYTHONUNBUFFERED=1
      - TZ=America/New_York
```

**Build and deploy:**
```bash
docker-compose build
docker-compose up -d
```

**Pros:** Faster container starts, all dependencies pre-installed  
**Cons:** Need to rebuild after code changes (can still use volumes for development)

### 9.2 Reduce Memory Usage

**If RAM is limited:**

Edit backend/main.py to use smaller batch sizes or lazy loading (already implemented).

### 9.3 Set Up Log Rotation

**Prevent logs from filling disk:**

```bash
# Create log rotation config
cat > /share/Container/deer-deterrent/logrotate.conf << 'EOF'
/share/Container/deer-deterrent/logs/*.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
EOF

# Add to cron (requires root)
# Or manually run: logrotate logrotate.conf
```

## Part 10: Next Steps

### After QNAP Setup is Complete:

1. ✅ **Container running and accessible locally**
   - Test: `curl http://QNAP-IP:8000/api/stats`

2. **Set up router port forwarding** (see QNAP_DEPLOYMENT.md)
   - External port 8000 → QNAP-IP:8000

3. **Configure GoDaddy DNS**
   - A record: deer-api.rndpig.com → Your public IP

4. **Update Vercel environment**
   - VITE_API_URL=http://deer-api.rndpig.com:8000

5. **Test full stack**
   - Frontend at deer.rndpig.com should connect to backend

6. **Future enhancements:**
   - Add HTTPS/SSL
   - Integrate Ring camera
   - Integrate Rainbird sprinklers
   - Set up database for history

## Quick Reference Card

**SSH into QNAP:**
```bash
ssh admin@YOUR-QNAP-IP
cd /share/Container/deer-deterrent
```

**Check status:**
```bash
docker-compose ps
docker stats deer-deterrent-api
```

**View logs:**
```bash
docker-compose logs -f deer-api
```

**Restart:**
```bash
docker-compose restart
```

**Update code:**
```bash
# Copy new files via SCP, then:
docker-compose restart
```

**Test API:**
```bash
curl http://localhost:8000/api/stats
curl http://localhost:8000/api/settings
```

**Emergency stop:**
```bash
docker-compose down
```

**Emergency start:**
```bash
docker-compose up -d
```

That's everything you need to get the QNAP backend up and running! Let me know when you're ready to proceed with the next steps.
