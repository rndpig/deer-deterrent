# QNAP Deployment Guide - Deer Deterrent Backend

This guide walks you through deploying the Deer Deterrent backend API to your QNAP NAS using Docker and exposing it via your GoDaddy domain.

## Prerequisites

### On Your QNAP:
1. **Container Station** installed and running
2. **SSH access** enabled (Control Panel → Network & File Services → Telnet/SSH)
3. At least **4GB RAM** available for the container
4. **Static IP** on your local network (or DHCP reservation)
5. **Port forwarding** configured on your router (Port 8000 → QNAP IP)

### On Your Computer:
1. SSH client (built into Windows 11)
2. GoDaddy account access for DNS management
3. This repository cloned and up-to-date

### On Your Router:
1. Port forwarding rule: External Port 8000 → QNAP Internal IP:8000
2. (Optional but recommended) Port 8443 for HTTPS if using SSL

## Step 1: Prepare the QNAP Environment

### 1.1 Connect via SSH
```powershell
ssh admin@YOUR-QNAP-IP
# Enter your admin password
```

### 1.2 Create Application Directory
```bash
# Create directory for the application
mkdir -p /share/Container/deer-deterrent
cd /share/Container/deer-deterrent

# Create subdirectories
mkdir -p models/production
mkdir -p logs
mkdir -p data
```

## Step 2: Transfer Files to QNAP

### 2.1 From Your Windows Machine

Option A - Using SCP (Secure Copy):
```powershell
# Navigate to your project
cd "C:\Users\rndpi\Documents\Coding Projects\deer-deterrent"

# Copy backend files
scp -r backend admin@YOUR-QNAP-IP:/share/Container/deer-deterrent/

# Copy source code
scp -r src admin@YOUR-QNAP-IP:/share/Container/deer-deterrent/

# Copy the trained model
scp models/production/best.pt admin@YOUR-QNAP-IP:/share/Container/deer-deterrent/models/production/
```

Option B - Using QNAP File Station:
1. Open QNAP File Station in browser: `http://YOUR-QNAP-IP:8080`
2. Navigate to `/Container/deer-deterrent`
3. Upload folders: `backend/`, `src/`, `models/production/`

## Step 3: Create Docker Compose File

SSH into QNAP and create the deployment configuration:

```bash
cd /share/Container/deer-deterrent

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
      - TZ=America/New_York  # Change to your timezone
    
    command: >
      bash -c "
        apt-get update &&
        apt-get install -y libgl1-mesa-glx libglib2.0-0 &&
        pip install --no-cache-dir -r /app/backend/requirements.txt &&
        cd /app &&
        uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
      "
    
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/api/stats')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

networks:
  default:
    name: deer-deterrent-network
EOF
```

## Step 4: Deploy with Container Station

### 4.1 Using Docker Compose
```bash
cd /share/Container/deer-deterrent
docker-compose up -d
```

This will:
- Download Python 3.11 image (~200MB)
- Install system dependencies
- Install all Python packages including PyTorch, YOLO, OpenCV (~2GB)
- Start the FastAPI server

**First run takes 10-15 minutes** to download and install everything.

### 4.2 Monitor the Installation
```bash
# Watch the logs to see progress
docker-compose logs -f deer-api

# Wait until you see:
# "INFO:     Application startup complete."
```

### 4.3 Verify Deployment
```bash
# Check container status
docker-compose ps

# Should show: State=Up

# Test the API locally on QNAP
curl http://localhost:8000/api/stats

# Expected output: {"total_detections": 0, "total_deer": 0, ...}
```

## Step 5: Configure Router Port Forwarding

### 5.1 Find Your QNAP's Local IP
```bash
# On QNAP via SSH
ip addr show | grep inet
```

Note the IP (e.g., 192.168.1.100)

### 5.2 Set Up Port Forwarding on Your Router

This varies by router, but generally:
1. Access your router admin panel (usually 192.168.1.1 or 192.168.0.1)
2. Find "Port Forwarding" or "Virtual Server" settings
3. Add rule:
   - **External Port**: 8000
   - **Internal IP**: Your QNAP IP (e.g., 192.168.1.100)
   - **Internal Port**: 8000
   - **Protocol**: TCP
   - **Description**: Deer API

### 5.3 Find Your Public IP
```powershell
# On your Windows machine
curl ifconfig.me
# Note this IP address
```

## Step 6: Configure GoDaddy DNS

### 6.1 Create A Record for API Subdomain

1. Log into GoDaddy: https://dnsmanagement.godaddy.com/
2. Select your domain: **rndpig.com**
3. Click **Add** → **A Record**
4. Configure:
   - **Type**: A
   - **Name**: deer-api
   - **Value**: Your public IP from Step 5.3
   - **TTL**: 600 seconds (10 minutes)
5. Click **Save**

DNS propagation takes 5-30 minutes.

### 6.2 Verify DNS Resolution
```powershell
# Wait a few minutes, then test
nslookup deer-api.rndpig.com

# Should show your public IP
```

## Step 7: Test External Access

### 7.1 Test from Your Computer
```powershell
# Test the API endpoint
curl http://deer-api.rndpig.com:8000/api/stats
```

If this works, your backend is accessible!

### 7.2 Common Issues

**Connection refused:**
- Check router port forwarding is enabled
- Verify QNAP firewall allows port 8000
- Confirm container is running: `docker-compose ps`

**DNS not resolving:**
- Wait longer (up to 30 minutes for DNS propagation)
- Clear DNS cache: `ipconfig /flushdns`
- Try `http://YOUR-PUBLIC-IP:8000/api/stats` directly

## Step 8: Update Vercel Environment Variables

1. Go to Vercel dashboard: https://vercel.com/rndpig/deer-deterrent
2. Navigate to **Settings** → **Environment Variables**
3. Find `VITE_API_URL` and update it to: `http://deer-api.rndpig.com:8000`
4. Save and redeploy:
   - Go to **Deployments** → Click latest → **⋮** → **Redeploy**

## Step 9: Test the Full Stack

### 9.1 Test Backend Directly
```powershell
# From your computer
curl http://deer-api.rndpig.com:8000/api/stats
curl http://deer-api.rndpig.com:8000/api/settings
```

### 9.2 Test Frontend
1. Open https://deer.rndpig.com
2. Sign in with your Google account
3. Go to Settings tab
4. Make a change and click "Save Settings"
5. Should now say "Settings saved successfully (backend and local)!"

### 9.3 Check Dashboard
The dashboard should show real data from the backend instead of "Error: Failed to fetch"

## Optional: Set Up HTTPS with Self-Signed Certificate

If you want HTTPS for the API (recommended for security):

### Create SSL Certificate on QNAP
```bash
# Install certbot (if not available)
# Or use QNAP's built-in certificate manager

# For development, create self-signed cert:
cd /share/Container/deer-deterrent
mkdir -p ssl

openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout ssl/key.pem \
  -out ssl/cert.pem \
  -days 365 \
  -subj "/CN=deer-api.rndpig.com"
```

### Update Docker Compose for HTTPS
```bash
# Add SSL volume and change command
# Update docker-compose.yml to use uvicorn with SSL options
# Port 8443 instead of 8000
```

## Step 10: Monitoring & Maintenance

### View Container Logs
```bash
# Real-time logs
docker-compose logs -f deer-api

# Last 100 lines
docker-compose logs --tail=100 deer-api
```

### Restart Container
```bash
cd /share/Container/deer-deterrent
docker-compose restart
```

### Update Code
```powershell
# On your Windows machine, after making changes:
cd "C:\Users\rndpi\Documents\Coding Projects\deer-deterrent"

# Push to GitHub
git add .
git commit -m "Backend updates"
git push

# On QNAP
ssh admin@YOUR-QNAP-IP
cd /share/Container/deer-deterrent

# Re-upload files via SCP or pull from git
scp -r backend admin@YOUR-QNAP-IP:/share/Container/deer-deterrent/

# Restart container to apply changes
docker-compose restart
```

### Monitor Resource Usage
```bash
# Container stats
docker stats deer-deterrent-api

# QNAP Resource Monitor
# Access via web UI: http://YOUR-QNAP-IP:8080
```

## Troubleshooting

### Container Won't Start
```bash
# Check logs for errors
docker-compose logs deer-api

# Common issues:
# 1. Port 8000 already in use
docker ps -a | grep 8000

# 2. Missing dependencies
docker-compose exec deer-api pip list

# 3. Model file not found
docker-compose exec deer-api ls -la /app/models/production/
```

### Cannot Access from Internet
1. **Check router port forwarding**: Log into router, verify rule exists
2. **Check QNAP firewall**: Control Panel → Security → Firewall → Allow port 8000
3. **Test locally first**: `curl http://localhost:8000/api/stats` from QNAP
4. **Test from LAN**: `curl http://QNAP-IP:8000/api/stats` from your PC
5. **Test public IP**: `curl http://YOUR-PUBLIC-IP:8000/api/stats`
6. **Finally test domain**: `curl http://deer-api.rndpig.com:8000/api/stats`

### Frontend Can't Connect
1. Check CORS settings in backend/main.py (should include https://deer.rndpig.com)
2. Verify VITE_API_URL in Vercel is `http://deer-api.rndpig.com:8000`
3. Check browser console for errors (F12)
4. Test backend directly: `curl http://deer-api.rndpig.com:8000/api/stats`

### Dynamic IP Issues
If your ISP changes your public IP frequently:
- Use a Dynamic DNS service (No-IP, DuckDNS, etc.)
- Or check with your ISP for a static IP option
- Update GoDaddy A record when IP changes

### High CPU/Memory Usage
YOLOv8 is resource-intensive:
- CPU mode uses ~2-4GB RAM
- Each detection uses significant CPU
- Monitor with: `docker stats deer-deterrent-api`

## Security Considerations

### Current Setup (HTTP)
- ⚠️ Traffic is unencrypted
- ✅ OAuth protects frontend access
- ⚠️ API is publicly accessible on port 8000

### Recommendations
1. Add API authentication/tokens for production
2. Use HTTPS with Let's Encrypt certificate
3. Consider VPN instead of port forwarding
4. Implement rate limiting on API endpoints

## Next Steps

After deployment:
1. ✅ Backend running on QNAP
2. ✅ Accessible via deer-api.rndpig.com
3. ✅ Frontend connected to backend
4. ⏳ Test deer detection with demo mode
5. ⏳ Integrate Ring camera feed
6. ⏳ Integrate Rainbird sprinkler control
7. ⏳ Set up database for detection history

## Quick Reference Commands

```bash
# SSH into QNAP
ssh admin@YOUR-QNAP-IP

# Navigate to project
cd /share/Container/deer-deterrent

# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f deer-api

# Restart after code changes
docker-compose restart

# Check status
docker-compose ps

# Test locally
curl http://localhost:8000/api/stats
```

## Support

If you encounter issues:
1. Check container logs: `docker-compose logs deer-api`
2. Test locally on QNAP: `curl http://localhost:8000/api/stats`
3. Test from LAN: `curl http://QNAP-IP:8000/api/stats`
4. Verify port forwarding in router
5. Check DNS resolution: `nslookup deer-api.rndpig.com`
6. Verify public IP hasn't changed


## Step 1: Prepare the QNAP Environment

### 1.1 Connect via SSH
```powershell
ssh admin@YOUR-QNAP-IP
# Enter your admin password
```

### 1.2 Create Application Directory
```bash
# Create directory for the application
mkdir -p /share/Container/deer-deterrent
cd /share/Container/deer-deterrent

# Create subdirectories
mkdir -p models/production
mkdir -p logs
mkdir -p data
```

## Step 2: Transfer Files to QNAP

### 2.1 From Your Windows Machine

Option A - Using SCP (Secure Copy):
```powershell
# Navigate to your project
cd "C:\Users\rndpi\Documents\Coding Projects\deer-deterrent"

# Copy backend files
scp -r backend admin@YOUR-QNAP-IP:/share/Container/deer-deterrent/

# Copy source code
scp -r src admin@YOUR-QNAP-IP:/share/Container/deer-deterrent/

# Copy the trained model
scp models/production/best.pt admin@YOUR-QNAP-IP:/share/Container/deer-deterrent/models/production/
```

Option B - Using QNAP File Station:
1. Open QNAP File Station in browser: `http://YOUR-QNAP-IP:8080`
2. Navigate to `/Container/deer-deterrent`
3. Upload folders: `backend/`, `src/`, `models/production/`

## Step 3: Create Docker Compose File

SSH into QNAP and create the deployment configuration:

```bash
cd /share/Container/deer-deterrent

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
      - TZ=America/New_York  # Change to your timezone
    
    command: >
      bash -c "
        apt-get update &&
        apt-get install -y libgl1-mesa-glx libglib2.0-0 &&
        pip install --no-cache-dir -r /app/backend/requirements.txt &&
        cd /app &&
        uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
      "
    
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/api/stats')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

networks:
  default:
    name: deer-deterrent-network
EOF
```

## Step 4: Update Backend CORS Settings

We need to allow the frontend domain. Edit the main.py file:

```bash
cd /share/Container/deer-deterrent/backend
vi main.py  # or use nano if you prefer
```

Find the CORS middleware section and update it:
```python
# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://deer.rndpig.com",
        "https://deer-deterrent.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Step 5: Deploy with Container Station

### 5.1 Using Docker Compose
```bash
cd /share/Container/deer-deterrent
docker-compose up -d
```

### 5.2 Verify Deployment
```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs -f deer-api

# Test the API
curl http://localhost:8000/api/stats
```

Expected output: JSON with stats like `{"total_detections": 0, ...}`

## Step 6: Set Up Cloudflare Tunnel

### 6.1 Install Cloudflared on QNAP
```bash
# Download cloudflared for Linux
cd /tmp
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64

# Make executable and move to system path
chmod +x cloudflared-linux-amd64
mv cloudflared-linux-amd64 /usr/local/bin/cloudflared

# Verify installation
cloudflared --version
```

### 6.2 Authenticate with Cloudflare
```bash
cloudflared tunnel login
```

This will print a URL. Open it in your browser and select your domain (rndpig.com).

### 6.3 Create the Tunnel
```bash
# Create tunnel
cloudflared tunnel create deer-api

# This creates a credentials file and shows the tunnel ID
# Note the tunnel ID - you'll need it
```

### 6.4 Configure the Tunnel
```bash
# Create config directory
mkdir -p /root/.cloudflared

# Create tunnel configuration
cat > /root/.cloudflared/config.yml << 'EOF'
tunnel: <YOUR-TUNNEL-ID>
credentials-file: /root/.cloudflared/<YOUR-TUNNEL-ID>.json

ingress:
  - hostname: deer-api.rndpig.com
    service: http://localhost:8000
  - service: http_status:404
EOF
```

### 6.5 Route DNS to Tunnel
```bash
# Create DNS record pointing to tunnel
cloudflared tunnel route dns deer-api deer-api.rndpig.com
```

### 6.6 Run the Tunnel
```bash
# Test the tunnel
cloudflared tunnel run deer-api

# If it works, stop it (Ctrl+C) and set it up as a service
```

### 6.7 Create Systemd Service (for auto-start)
```bash
cat > /etc/systemd/system/cloudflared-deer-api.service << 'EOF'
[Unit]
Description=Cloudflare Tunnel - Deer API
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel --no-autoupdate run deer-api
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
systemctl daemon-reload
systemctl enable cloudflared-deer-api
systemctl start cloudflared-deer-api

# Check status
systemctl status cloudflared-deer-api
```

## Step 7: Update Vercel Environment Variables

1. Go to Vercel dashboard: https://vercel.com/rndpig/deer-deterrent
2. Navigate to **Settings** → **Environment Variables**
3. Find `VITE_API_URL` and update it to: `https://deer-api.rndpig.com`
4. Save and redeploy:
   ```
   Deployments → Latest → ⋮ → Redeploy
   ```

## Step 8: Test the Full Stack

### 8.1 Test Backend Directly
```bash
# From QNAP SSH or your computer
curl https://deer-api.rndpig.com/api/stats
curl https://deer-api.rndpig.com/api/settings
```

### 8.2 Test Frontend
1. Open https://deer.rndpig.com
2. Sign in with your Google account
3. Go to Settings tab
4. Make a change and click "Save Settings"
5. Should now say "Settings saved successfully (backend and local)!"

### 8.3 Check Dashboard
The dashboard should show real data from the backend instead of "Error: Failed to fetch"

## Step 9: Monitoring & Maintenance

### View Container Logs
```bash
# Real-time logs
docker-compose logs -f deer-api

# Last 100 lines
docker-compose logs --tail=100 deer-api
```

### Restart Container
```bash
cd /share/Container/deer-deterrent
docker-compose restart
```

### Update Code
```powershell
# On your Windows machine, after making changes:
cd "C:\Users\rndpi\Documents\Coding Projects\deer-deterrent"

# Push to GitHub
git add .
git commit -m "Backend updates"
git push

# On QNAP, pull changes
cd /share/Container/deer-deterrent
git pull  # If you cloned the repo
# OR re-upload files via SCP

# Restart container to apply changes
docker-compose restart
```

### Monitor Resource Usage
```bash
# Container stats
docker stats deer-deterrent-api

# QNAP Resource Monitor
# Access via web UI: http://YOUR-QNAP-IP:8080
```

## Troubleshooting

### Container Won't Start
```bash
# Check logs for errors
docker-compose logs deer-api

# Common issues:
# 1. Port 8000 already in use
docker ps -a | grep 8000

# 2. Missing dependencies
docker-compose exec deer-api pip list

# 3. Model file not found
docker-compose exec deer-api ls -la /app/models/production/
```

### Tunnel Issues
```bash
# Check tunnel status
cloudflared tunnel info deer-api

# Test tunnel connectivity
cloudflared tunnel route lb get deer-api.rndpig.com

# Restart tunnel
systemctl restart cloudflared-deer-api
```

### Frontend Can't Connect
1. Check CORS settings in backend/main.py
2. Verify VITE_API_URL in Vercel
3. Check browser console for errors (F12)
4. Test backend directly: `curl https://deer-api.rndpig.com/api/stats`

### High CPU/Memory Usage
YOLOv8 is resource-intensive:
- CPU mode uses ~2-4GB RAM
- For better performance, consider GPU support
- Monitor with: `docker stats deer-deterrent-api`

## Security Considerations

1. **QNAP Firewall**: Only port 22 (SSH) needs to be open externally
2. **Cloudflare Tunnel**: All traffic encrypted, no ports exposed
3. **OAuth**: Only rndpig@gmail.com can access the dashboard
4. **HTTPS**: Cloudflare provides SSL automatically

## Next Steps

After deployment:
1. Test deer detection with demo mode
2. Integrate Ring camera feed (requires API research)
3. Integrate Rainbird sprinkler control
4. Set up database for detection history
5. Configure real camera zones

## Quick Reference Commands

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Restart after code changes
docker-compose restart

# Check tunnel status
systemctl status cloudflared-deer-api

# Manual tunnel run (for debugging)
cloudflared tunnel run deer-api
```

## Support

If you encounter issues:
1. Check container logs: `docker-compose logs deer-api`
2. Check tunnel logs: `journalctl -u cloudflared-deer-api -f`
3. Test backend directly: `curl http://localhost:8000/api/stats`
4. Verify DNS: `nslookup deer-api.rndpig.com`
