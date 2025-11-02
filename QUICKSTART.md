# Quick Start Guide

## ✅ System is Running!

### Access the Dashboard
Open your browser to: **http://localhost:5173**

You should see the Deer Deterrent Dashboard with 3 tabs:
- Dashboard
- Detection History  
- Settings

### Load Demo Data

1. Click the **"Load Demo Data"** button on the Dashboard
2. This will populate the system with test detections
3. You'll see stats update and recent activity appear

### What's Working

✅ **Backend API** (http://localhost:8000)
- REST API endpoints
- WebSocket for real-time updates
- Demo data loading
- Settings management

✅ **Frontend Dashboard** (http://localhost:5173)
- Real-time stats display
- Detection history with filtering
- Settings configuration panel
- Responsive design

⚠️ **Not Yet Available** (until dependencies installed):
- Live deer detection (needs OpenCV/PyTorch)
- Image annotation
- Ring camera integration
- Rainbird sprinkler control

### Testing the Dashboard

1. **Dashboard Tab**: View system stats and recent detections
2. **Detection History Tab**: Filter and browse all detections
3. **Settings Tab**: Configure confidence threshold, seasonal dates, sprinkler settings

### Next Steps

#### Install ML Dependencies (Optional - for full features)
```powershell
python -m pip install torch torchvision opencv-python ultralytics
```

Note: This requires ~2GB download and may need Visual Studio C++ Build Tools.

#### Deploy to Production

**Frontend (Vercel)**:
1. Push code to GitHub
2. Import repository in Vercel
3. Set root directory: `frontend/`
4. Add environment variable: `VITE_API_URL=https://your-backend-url`
5. Deploy!

**Backend (QNAP NAS)**:
See `DEPLOYMENT.md` for full Docker + Cloudflare Tunnel setup.

### Troubleshooting

**Backend won't start**:
- Check port 8000 isn't already in use
- Verify FastAPI is installed: `python -m pip list | findstr fastapi`

**Frontend won't start**:
- Check port 5173 isn't already in use
- Run `npm install` in frontend directory

**Can't connect to backend**:
- Verify backend is running on http://localhost:8000
- Check backend terminal for errors
- Test directly: Open http://localhost:8000 in browser

**WebSocket not connecting**:
- Some firewalls block WebSocket connections
- Try disabling firewall temporarily
- Check browser console for errors (F12)

### Development Workflow

1. **Make changes** to frontend code in `frontend/src/`
2. **Save** - Vite will hot-reload automatically
3. **Make changes** to backend code in `backend/main.py`
4. **Save** - Uvicorn will auto-reload

### Stopping the Servers

Press **Ctrl+C** in each terminal window to stop the servers.

### Questions?

- Backend API docs: http://localhost:8000/docs (FastAPI auto-generated)
- Check README.md for architecture overview
- See DEPLOYMENT.md for production deployment guide

Enjoy! 🦌 💦
