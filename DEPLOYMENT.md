# Deployment Guide

## Architecture

- **Frontend**: Vercel (React + Vite) - https://deer.rndpig.com
- **Backend**: QNAP NAS (Docker + FastAPI) - Accessed via Cloudflare Tunnel
- **Model**: YOLOv8n on QNAP (CPU inference)
- **Database**: SQLite on QNAP (future: PostgreSQL)

## Prerequisites

- QNAP NAS with Container Station installed
- Cloudflare account
- Vercel account
- GitHub repository

## Step 1: QNAP NAS Setup

### Install Docker on QNAP

1. Open QNAP App Center
2. Install "Container Station"
3. Enable SSH access in QNAP settings

### Deploy Backend Container

```bash
# SSH into QNAP
ssh admin@your-qnap-ip

# Create project directory
mkdir -p /share/Container/deer-deterrent
cd /share/Container/deer-deterrent

# Clone repository
git clone https://github.com/rndpig/deer-deterrent.git
cd deer-deterrent

# Copy .env file with credentials
nano .env

# Build and run with Docker Compose
docker-compose up -d backend

# Check logs
docker-compose logs -f backend
```

## Step 2: Cloudflare Tunnel

### Install cloudflared on QNAP

```bash
# Download cloudflared
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
chmod +x cloudflared-linux-amd64
sudo mv cloudflared-linux-amd64 /usr/local/bin/cloudflared

# Login to Cloudflare
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create deer-api

# Configure tunnel
nano ~/.cloudflared/config.yml
```

Add this configuration:

```yaml
tunnel: <tunnel-id>
credentials-file: /root/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: deer-api.rndpig.com
    service: http://localhost:8000
  - service: http_status:404
```

### Route DNS

```bash
# Route DNS to tunnel
cloudflared tunnel route dns deer-api deer-api.rndpig.com

# Run tunnel as service
cloudflared service install
systemctl start cloudflared
systemctl enable cloudflared
```

## Step 3: Vercel Deployment

### Connect Repository

1. Go to https://vercel.com
2. Click "Add New Project"
3. Import `rndpig/deer-deterrent` repository
4. Set root directory to `frontend/`

### Configure Environment Variables

Add in Vercel dashboard:

```
VITE_API_URL=https://deer-api.rndpig.com
```

### Deploy

1. Vercel auto-deploys from `main` branch
2. Each push triggers new deployment
3. Preview deployments for pull requests

### Custom Domain

1. Add custom domain in Vercel: `deer.rndpig.com`
2. Update DNS in Cloudflare:
   - Type: CNAME
   - Name: deer
   - Target: cname.vercel-dns.com
   - Proxy: ON (orange cloud)

## Step 4: Testing

### Backend Health Check

```bash
curl https://deer-api.rndpig.com/api/health
```

Should return:
```json
{
  "status": "healthy",
  "detector": "ready",
  "websocket_clients": 0,
  "uptime": "running"
}
```

### Frontend Access

Visit https://deer.rndpig.com

Should see dashboard with:
- System stats
- Recent detections
- Settings panel

### Load Demo Data

In dashboard, click "Load Demo Data" button to populate with test detections.

## Step 5: Monitoring

### QNAP Container Station

1. Open Container Station
2. Check `deer-deterrent-backend` container status
3. View logs and resource usage

### Cloudflare Analytics

1. Go to Cloudflare dashboard
2. Check tunnel status
3. View traffic analytics

### Vercel Analytics

1. Go to Vercel dashboard
2. Check deployment status
3. View function logs

## Troubleshooting

### Backend won't start

```bash
# Check logs
docker-compose logs backend

# Rebuild container
docker-compose down
docker-compose up -d --build backend
```

### Cloudflare tunnel disconnected

```bash
# Check status
systemctl status cloudflared

# Restart service
systemctl restart cloudflared

# Check logs
journalctl -u cloudflared -f
```

### Frontend can't reach backend

1. Check `VITE_API_URL` in Vercel env vars
2. Verify Cloudflare tunnel is running
3. Check CORS settings in `backend/main.py`
4. Test backend directly: `curl https://deer-api.rndpig.com`

## Updating

### Backend Updates

```bash
# SSH into QNAP
cd /share/Container/deer-deterrent

# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build backend
```

### Frontend Updates

Just push to GitHub - Vercel auto-deploys from `main` branch!

## Security

- `.env` file with credentials NOT committed to git
- HTTPS enforced via Cloudflare
- QNAP behind firewall, only tunnel exposed
- Vercel handles frontend security headers

## Backup

### Model and Data

```bash
# Backup from QNAP
scp -r admin@qnap-ip:/share/Container/deer-deterrent/models ./backup/
scp -r admin@qnap-ip:/share/Container/deer-deterrent/temp ./backup/
```

### Database (when implemented)

```bash
# SQLite backup
docker exec deer-deterrent-backend sqlite3 /app/data/detections.db ".backup /app/backup/detections-$(date +%Y%m%d).db"
```
