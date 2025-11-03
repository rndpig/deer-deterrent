# QNAP Deployment Guide - Deer Deterrent Backend

This guide walks you through deploying the Deer Deterrent backend API to your QNAP NAS using Docker and exposing it securely via Cloudflare Tunnel.

## Prerequisites

### On Your QNAP:
1. **Container Station** installed and running
2. **SSH access** enabled (Control Panel → Network & File Services → Telnet/SSH)
3. At least **4GB RAM** available for the container
4. **Docker Compose** support (built into Container Station)

### On Your Computer:
1. SSH client (built into Windows 11)
2. Cloudflare account with your domain (rndpig.com)
3. This repository cloned and up-to-date

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
