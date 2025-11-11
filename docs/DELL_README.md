# 🖥️ Dell OptiPlex Deployment - Overview

Your Dell OptiPlex 9020 is an **excellent choice** for running the deer deterrent system! This guide will help you get started.

---

## 📊 Why Dell OptiPlex is Better Than Raspberry Pi

| Feature | Dell OptiPlex 9020 | Raspberry Pi 4 |
|---------|-------------------|----------------|
| **CPU** | Intel i7-4790 (4c/8t @ 3.6GHz) | ARM Cortex-A72 (4c @ 1.5GHz) |
| **RAM** | 16GB DDR3 | 2-8GB |
| **Storage** | 256GB SSD | MicroSD (slow) |
| **ML Inference** | **2-5 seconds** | 10-20 seconds |
| **Power Cost** | ~$40/year | ~$5/year |
| **Reliability** | Excellent | Excellent |
| **Setup** | Easier (standard x86) | Medium |
| **Multi-Service** | ✅ All services on one machine | Limited by resources |
| **Future-Proof** | ✅ Room for expansion | Limited |

**Verdict:** Dell is the better choice for faster detection and future expansion. The $35/year extra power cost is worth it!

---

## 🚀 Quick Links - Choose Your Path

### 📖 New to Linux/Docker?
**Start here:** [`QUICKSTART_DELL.md`](QUICKSTART_DELL.md)
- Fastest way to get running
- Step-by-step with minimal explanations
- Copy-paste commands
- **Time: ~2 hours**

### 📚 Want to Understand Everything?
**Read this:** [`DELL_DEPLOYMENT.md`](DELL_DEPLOYMENT.md)
- Comprehensive guide with explanations
- Covers every detail
- Troubleshooting tips
- Best practices
- **Time: Read through, then ~2 hours to implement**

### ✅ Want to Track Progress?
**Use this:** [`DELL_CHECKLIST.md`](DELL_CHECKLIST.md)
- Interactive checklist
- Track completed steps
- Fill in your specific details
- Reference for later
- **Use alongside the other guides**

---

## 🎯 What You'll Build

A complete AI-powered deer deterrent system running on a single Dell PC:

```
┌────────────────────────────────────────────────────────────┐
│              Dell OptiPlex 9020 (Ubuntu Server)            │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Frontend │  │ Backend  │  │    ML    │  │  Ring    │  │
│  │ Dashboard│  │   API    │  │ Detector │  │  Camera  │  │
│  │  :3000   │  │  :8000   │  │  :8001   │  │  :55123  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Coordinator│ │ Database │  │   MQTT   │  │  Logs &  │  │
│  │ Sprinkler│  │PostgreSQL│  │  Broker  │  │Snapshots │  │
│  │  :5000   │  │  :5432   │  │  :1883   │  │          │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
│            All managed by Docker Compose                   │
└────────────────────────────────────────────────────────────┘
```

**Features:**
- ✅ Real-time deer detection using YOLOv8
- ✅ Ring camera integration via MQTT
- ✅ Automatic sprinkler activation
- ✅ Web dashboard for monitoring
- ✅ Detection history and analytics
- ✅ Configurable cooldown periods
- ✅ Time-based activation rules
- ✅ All data stored locally

---

## ⚡ Super Quick Start (5-Minute Overview)

1. **Install Ubuntu Server 24.04 LTS** on Dell (30 min)
2. **Set static IP** (192.168.1.200 or your choice)
3. **Install Docker** (5 min)
4. **Clone repo and configure** (10 min)
5. **Deploy with docker-compose** (15 min)
6. **Configure Ring and Rainbird** (20 min)
7. **Test and go live** (30 min)

**Total time: ~2 hours**

---

## 📋 Prerequisites

### Hardware You Need:
- ✅ Dell OptiPlex 9020 (your machine!)
- ✅ Monitor + keyboard + mouse (for initial setup)
- ✅ 8GB+ USB flash drive (will be erased)
- ✅ Ethernet cable connected to router

### Information You Need:
- ✅ Ring account credentials + 2FA method
- ✅ Rainbird controller IP (we'll help you find it)
- ✅ Router admin access (for static IP)

### Software to Download (on Windows PC):
- ✅ Ubuntu Server 24.04 LTS ISO (~2.6GB)
- ✅ Rufus (USB creation tool)

---

## 🎬 Installation Flow

```
1. Prepare USB Drive (Windows PC)
   ↓
2. Install Ubuntu (Dell OptiPlex)
   ↓
3. Configure Network (SSH from Windows)
   ↓
4. Install Docker (SSH)
   ↓
5. Deploy Deer Deterrent (SSH)
   ↓
6. Configure Ring Cameras (Browser)
   ↓
7. Configure Rainbird (SSH)
   ↓
8. Test System (Browser + SSH)
   ↓
9. Go Live! 🎉
```

---

## 🛠️ Daily Management

Once deployed, manage your system with the `manage.sh` script:

```bash
# Start all services
./manage.sh start

# Check status
./manage.sh status

# View logs
./manage.sh logs coordinator

# Check health
./manage.sh health

# Monitor live
./manage.sh monitor

# Update system
./manage.sh update

# Backup data
./manage.sh backup

# Get help
./manage.sh help
```

---

## 📂 File Structure

After deployment, your directory structure will look like:

```
deer-deterrent/
├── QUICKSTART_DELL.md           ← Start here!
├── DELL_DEPLOYMENT.md            ← Detailed guide
├── DELL_CHECKLIST.md             ← Track progress
├── docker-compose.dell.yml       ← Main deployment config
├── .env.dell                     ← Your configuration (you create)
├── manage.sh                     ← Management script
├── Dockerfile.ml-detector        ← ML service container
├── Dockerfile.coordinator        ← Coordinator service container
│
├── dell-deployment/              ← Runtime data
│   ├── logs/                     ← Service logs
│   ├── data/
│   │   ├── snapshots/           ← Camera images
│   │   └── database/            ← PostgreSQL data
│   ├── models/                   ← YOLO models
│   ├── ring-mqtt/                ← Ring integration data
│   └── mosquitto/                ← MQTT broker data
│
├── backend/                      ← Backend API code
├── frontend/                     ← Dashboard UI code
├── src/                          ← Core application code
└── configs/                      ← Configuration files
```

---

## 🌐 Access Points

After deployment, access your system at:

| Service | URL | Purpose |
|---------|-----|---------|
| **Dashboard** | http://192.168.1.200:3000 | Main UI - view detections, settings |
| **Backend API** | http://192.168.1.200:8000/docs | API documentation (Swagger) |
| **ML Detector** | http://192.168.1.200:8001/docs | ML API documentation |
| **Ring Config** | http://192.168.1.200:55123 | Ring camera authentication |
| **SSH Access** | ssh deer@192.168.1.200 | Command line access |

---

## ⚙️ Configuration Quick Reference

Main settings in `.env.dell`:

```bash
# Network
DELL_SERVER_IP=192.168.1.200

# Ring
RING_USERNAME=your-email@example.com
RING_REFRESH_TOKEN=<get from Ring MQTT UI>

# Rainbird
RAINBIRD_IP=192.168.1.XXX
RAINBIRD_ZONE=1
RAINBIRD_DURATION_SECONDS=30

# Detection
CONFIDENCE_THRESHOLD=0.75      # Higher = fewer false positives
COOLDOWN_SECONDS=300           # 5 minutes between activations
ENABLE_SPRINKLER=false         # Start with false for testing!

# Time-based (24-hour format)
ACTIVE_HOURS_START=0           # 0 = midnight
ACTIVE_HOURS_END=24            # 24 = always active

# Security (CHANGE THESE!)
POSTGRES_PASSWORD=ChangeMe123!
JWT_SECRET_KEY=ChangeMe789!
```

---

## 🧪 Testing Before Going Live

**IMPORTANT:** Always test with `ENABLE_SPRINKLER=false` first!

1. Deploy system with sprinkler disabled
2. Trigger Ring camera motion
3. Check logs: `./manage.sh logs coordinator`
4. Verify deer detection works
5. Monitor for 2-3 days
6. Adjust `CONFIDENCE_THRESHOLD` if needed
7. Then enable sprinkler: `ENABLE_SPRINKLER=true`

---

## 🐛 Common Issues

### "Can't access dashboard"
- Check Dell IP is correct: `ip addr show`
- Try from Dell: `curl http://localhost:3000`
- Check firewall: `sudo ufw status`

### "Ring not connecting"
- Token expired (every 6 months)
- Re-authenticate: http://192.168.1.200:55123
- Update `RING_REFRESH_TOKEN` in `.env.dell`

### "ML detection slow"
- 2-5 seconds is normal on CPU
- Check: `docker stats` for resource usage
- Use smaller model if needed: `yolov8n.pt`

### "Out of disk space"
- Clean Docker: `./manage.sh clean`
- Remove old snapshots: `rm dell-deployment/data/snapshots/*-old.jpg`
- Check usage: `df -h`

---

## 📊 Performance Expectations

On Dell OptiPlex 9020:
- **ML Inference:** 2-5 seconds per image
- **End-to-end latency:** 3-7 seconds (motion → sprinkler)
- **CPU usage:** 20-40% during detection
- **RAM usage:** 4-6 GB total
- **Disk usage:** ~2-5 GB (grows with snapshots)
- **Power consumption:** ~35-45W idle, ~65W during detection

---

## 🔄 Update Process

To update the system:

```bash
cd ~/deer-deterrent
./manage.sh update
```

This will:
1. Pull latest code from GitHub
2. Rebuild containers with updates
3. Restart services
4. Preserve your data and configuration

---

## 💾 Backup Strategy

**Automated backups:**
```bash
# Set up daily backup at 2 AM
crontab -e
# Add: 0 2 * * * /home/deer/deer-deterrent/manage.sh backup
```

**Manual backup:**
```bash
./manage.sh backup
```

Backups include:
- Database (PostgreSQL dump)
- Configuration (.env.dell)
- Snapshots and logs (tar.gz)

Backups stored in: `~/backups/`

---

## 📈 Next Steps After Deployment

1. **Week 1:** Monitor daily, adjust confidence threshold
2. **Week 2:** Fine-tune cooldown and active hours
3. **Week 3:** Review false positive/negative rate
4. **Month 1:** Consider training custom model with your deer images
5. **Ongoing:** Weekly health checks, monthly updates

---

## 🎓 Learning Resources

- **Docker Basics:** https://docs.docker.com/get-started/
- **Ubuntu Server:** https://ubuntu.com/server/docs
- **YOLOv8 Documentation:** https://docs.ultralytics.com/
- **Ring API (unofficial):** https://github.com/dgreif/ring
- **FastAPI:** https://fastapi.tiangolo.com/

---

## 🤝 Support

**Documentation:**
- Quick start: `QUICKSTART_DELL.md`
- Full guide: `DELL_DEPLOYMENT.md`
- Checklist: `DELL_CHECKLIST.md`
- Main README: `README.md`

**Troubleshooting:**
- Check logs: `./manage.sh logs`
- Health check: `./manage.sh health`
- See troubleshooting section in `DELL_DEPLOYMENT.md`

**Community:**
- GitHub Issues: https://github.com/rndpig/deer-deterrent/issues

---

## ✅ Success Criteria

Your system is fully operational when:
- ✅ All services show "Up" status
- ✅ Dashboard loads and shows data
- ✅ Ring cameras connected and sending events
- ✅ ML detector successfully identifies deer
- ✅ Sprinklers activate when deer detected
- ✅ Events logged to database
- ✅ Cooldown prevents activation spam
- ✅ System stable for 7+ days
- ✅ Backups running automatically

---

## 🎉 Ready to Start?

**Choose your path:**

1. **Fast track:** [`QUICKSTART_DELL.md`](QUICKSTART_DELL.md) - Get running in 2 hours
2. **Learn as you go:** [`DELL_DEPLOYMENT.md`](DELL_DEPLOYMENT.md) - Understand everything
3. **Track progress:** [`DELL_CHECKLIST.md`](DELL_CHECKLIST.md) - Don't miss any steps

**Recommended: Read QUICKSTART first, then follow DELL_DEPLOYMENT with CHECKLIST open.**

---

## 💡 Pro Tips

1. **Start with ENABLE_SPRINKLER=false** - Test thoroughly before activating sprinklers
2. **Monitor for a week** - Understand your false positive rate
3. **Adjust confidence threshold** - Find the sweet spot for your environment
4. **Set active hours** - Maybe only run at night when deer are active
5. **Use cooldown wisely** - 5-10 minutes prevents excessive water usage
6. **Save your passwords** - Store in a password manager, not just .env.dell
7. **Test your backup** - Actually try restoring to verify backups work

---

**Let's build this! 🦌💦**

Your Dell OptiPlex is about to become the smartest deer deterrent on the block. With faster processing than a Raspberry Pi and room to grow, you've made an excellent choice.

**Ready? Start with [`QUICKSTART_DELL.md`](QUICKSTART_DELL.md)!**
