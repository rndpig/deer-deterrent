# 🎯 Dell OptiPlex - Quick Reference Card

**Print this page and keep it handy!**

---

## 📍 Essential Information

**Dell Static IP:** `192.168.1.200` (or your chosen IP: `_____________`)

**SSH Access:** `ssh deer@192.168.1.200`

**Project Directory:** `/home/deer/deer-deterrent`

---

## 🌐 Web Access Points

| Service | URL |
|---------|-----|
| Dashboard | http://192.168.1.200:3000 |
| Backend API | http://192.168.1.200:8000/docs |
| ML Detector | http://192.168.1.200:8001/docs |
| Ring Config | http://192.168.1.200:55123 |

---

## 🚀 Essential Commands

### Daily Operations
```bash
# Start everything
./manage.sh start

# Check status
./manage.sh status

# View logs (all services)
./manage.sh logs

# View logs (specific service)
./manage.sh logs coordinator
./manage.sh logs ml-detector
./manage.sh logs ring-mqtt

# Health check
./manage.sh health

# Live monitoring
./manage.sh monitor

# Get help
./manage.sh help
```

### Service Control
```bash
# Restart all
./manage.sh restart

# Restart specific service
docker compose -f docker-compose.dell.yml restart coordinator

# Stop all
./manage.sh stop

# Start all
./manage.sh start
```

### Maintenance
```bash
# Update system
./manage.sh update

# Backup data
./manage.sh backup

# Clean Docker cache
./manage.sh clean

# Check resource usage
./manage.sh stats
```

---

## ⚙️ Configuration File

**Location:** `/home/deer/deer-deterrent/.env.dell`

**Edit:** `nano .env.dell`

**After editing, restart services:**
```bash
docker compose -f docker-compose.dell.yml restart
```

---

## 🔧 Key Settings to Tune

| Setting | Default | Purpose | Adjust If... |
|---------|---------|---------|--------------|
| CONFIDENCE_THRESHOLD | 0.75 | Detection sensitivity | Too many false positives → increase to 0.80-0.85<br>Missing deer → decrease to 0.65-0.70 |
| COOLDOWN_SECONDS | 300 | Time between activations | Activating too often → increase to 600<br>Need faster response → decrease to 180 |
| ENABLE_SPRINKLER | false | Actually activate sprinkler | Start with false, test, then set to true |
| ACTIVE_HOURS_START | 0 | When to start (24h) | Only want night → set to 18 (6 PM) |
| ACTIVE_HOURS_END | 24 | When to stop (24h) | Only want night → set to 6 (6 AM) |
| RAINBIRD_DURATION_SECONDS | 30 | Sprinkler run time | Too short/long → adjust as needed |

---

## 🐛 Quick Troubleshooting

### Services Won't Start
```bash
docker compose -f docker-compose.dell.yml logs
# Check for error messages
```

### Can't Access Dashboard
```bash
# Check if running
docker ps

# Check from Dell itself
curl http://localhost:3000

# Restart frontend
docker compose -f docker-compose.dell.yml restart frontend
```

### Ring Not Connecting
```bash
# Check logs
docker compose -f docker-compose.dell.yml logs ring-mqtt

# Token expired? Re-authenticate:
# Open: http://192.168.1.200:55123
# Get new token, update .env.dell, restart
```

### ML Detection Slow/Failing
```bash
# Check ML detector logs
docker compose -f docker-compose.dell.yml logs ml-detector

# Check if model loaded
curl http://localhost:8001/health

# Restart if needed
docker compose -f docker-compose.dell.yml restart ml-detector
```

### Out of Disk Space
```bash
# Check usage
df -h

# Clean Docker
./manage.sh clean

# Remove old snapshots
rm dell-deployment/data/snapshots/*-old.jpg
```

---

## 📊 System Health Checks

```bash
# Quick health check all services
./manage.sh health

# Check resource usage
./manage.sh stats

# View recent activity
./manage.sh logs --tail=50 coordinator

# Check disk space
df -h /

# Check memory
free -h

# Check Docker status
docker ps
```

---

## 🔄 Update Process

```bash
cd ~/deer-deterrent
./manage.sh update
# This pulls latest code and rebuilds containers
```

---

## 💾 Backup Process

```bash
# Manual backup
./manage.sh backup

# Backups stored in: ~/backups/

# Set up automated daily backup (2 AM)
crontab -e
# Add: 0 2 * * * /home/deer/deer-deterrent/manage.sh backup
```

---

## 🔐 Important Files

| File | Location | Purpose |
|------|----------|---------|
| Environment | .env.dell | Your configuration |
| Docker Compose | docker-compose.dell.yml | Service definitions |
| Management Script | manage.sh | Daily operations |
| Logs | dell-deployment/logs/ | Service logs |
| Snapshots | dell-deployment/data/snapshots/ | Camera images |
| Database | dell-deployment/data/database/ | PostgreSQL data |
| Models | dell-deployment/models/ | YOLO models |

---

## 📱 Ring Token Refresh

**Tokens expire every ~6 months**

When Ring stops working:
1. Open http://192.168.1.200:55123
2. Click "Get Ring Token"
3. Log in to Ring + complete 2FA
4. Copy new token
5. `nano .env.dell` → Update RING_REFRESH_TOKEN
6. `docker compose -f docker-compose.dell.yml restart ring-mqtt`

---

## 🎯 Performance Targets

| Metric | Target | Check Command |
|--------|--------|---------------|
| ML Inference | 2-5 seconds | Check logs for timing |
| End-to-end | <7 seconds | Test webhook |
| CPU Usage | <50% | `./manage.sh stats` |
| RAM Usage | <8 GB | `./manage.sh stats` |
| Disk Usage | <80% | `df -h` |
| Uptime | >99% | `uptime` |

---

## 🚨 Emergency Commands

### Stop Everything Immediately
```bash
docker compose -f docker-compose.dell.yml down
```

### Restart Everything
```bash
docker compose -f docker-compose.dell.yml restart
```

### View All Containers (including stopped)
```bash
docker ps -a
```

### Remove All Containers (nuclear option)
```bash
docker compose -f docker-compose.dell.yml down -v
# WARNING: This removes database data!
```

### System Reboot
```bash
sudo reboot
# Services auto-start on boot
```

---

## 📞 Documentation Quick Links

- **Overview:** DELL_README.md
- **Quick Start:** QUICKSTART_DELL.md
- **Full Guide:** DELL_DEPLOYMENT.md
- **Checklist:** DELL_CHECKLIST.md
- **This Card:** DELL_REFERENCE.md

---

## 📝 My Notes

**Rainbird Controller:**
- IP: `_____________`
- Model: `_____________`
- Zone 1: `_____________`
- Zone 2: `_____________`

**Ring Cameras:**
- Camera 1: `_____________` (ID: `_____________`)
- Camera 2: `_____________` (ID: `_____________`)

**Last Maintenance:**
- Backup: `_____________`
- Update: `_____________`
- Ring Token Refresh: `_____________`

**Important Dates:**
- Deployed: `_____________`
- Next Ring Token Refresh: `_____________` (6 months from deploy)

**Customizations:**
- Confidence Threshold: `_____________`
- Cooldown: `_____________` seconds
- Active Hours: `_____________` to `_____________`
- Sprinkler Duration: `_____________` seconds

---

## ✅ Weekly Checklist

- [ ] Check service status: `./manage.sh status`
- [ ] Review logs for errors: `./manage.sh logs | grep -i error`
- [ ] Check disk space: `df -h`
- [ ] Verify backups exist: `ls -lh ~/backups/`
- [ ] Test dashboard access: http://192.168.1.200:3000
- [ ] Review detection accuracy in dashboard
- [ ] Check for false positives/negatives

---

## 🎯 Monthly Checklist

- [ ] Update system: `sudo apt update && sudo apt upgrade -y`
- [ ] Update containers: `./manage.sh update`
- [ ] Review resource usage trends: `./manage.sh stats`
- [ ] Test backup restoration (important!)
- [ ] Clean old snapshots if disk getting full
- [ ] Check Docker disk usage: `docker system df`
- [ ] Review and adjust confidence threshold if needed

---

**Print this page and keep it near your workspace!**

*For detailed instructions, see the full guides in the repository.*
