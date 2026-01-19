"""
Diagnose the backend detector initialization issue.
"""
import requests
import json

API_URL = "https://deer-api.rndpig.com"

def diagnose_backend():
    """Check backend health and detector status."""
    
    print("="*80)
    print("Backend Detector Initialization Diagnosis")
    print("="*80)
    print()
    
    # 1. Check if backend is running
    print("1. Checking if backend API is responding...")
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            print("   ✓ Backend API is running")
            health = response.json()
            print(f"   Status: {health.get('status', 'unknown')}")
            print()
        else:
            print(f"   ⚠ Backend returned status {response.status_code}")
            print()
    except Exception as e:
        print(f"   ❌ Backend not responding: {e}")
        print()
        return
    
    # 2. Try to get videos (should work even without detector)
    print("2. Testing basic API functionality...")
    try:
        response = requests.get(f"{API_URL}/api/videos", timeout=5)
        if response.status_code == 200:
            videos = response.json()
            print(f"   ✓ Videos endpoint working ({len(videos)} videos)")
            print()
        else:
            print(f"   ⚠ Videos endpoint returned {response.status_code}")
            print()
    except Exception as e:
        print(f"   ⚠ Videos endpoint failed: {e}")
        print()
    
    # 3. Check backend logs for detector initialization
    print("3. Checking backend logs for detector errors...")
    print()
    print("   To check backend logs on server, run:")
    print("   ssh dilger")
    print("   sudo journalctl -u deer-backend -n 100 --no-pager | grep -i detector")
    print()
    print("   Or check the log file:")
    print("   ssh dilger")
    print("   tail -50 /home/rndpig/logs/backend.log | grep -i detector")
    print()
    
    # 4. Provide solutions
    print("="*80)
    print("Likely Causes and Solutions")
    print("="*80)
    print()
    print("The 'Detector not initialized' error means the backend couldn't load")
    print("the YOLOv8 model. This could be due to:")
    print()
    print("Issue 1: Missing Model Files")
    print("   Check if model exists on server:")
    print("   ssh dilger")
    print("   ls -lh /home/rndpig/deer-deterrent/models/production/best.pt")
    print("   ls -lh /home/rndpig/deer-deterrent/yolov8n.pt")
    print()
    print("   If missing, copy from local:")
    print("   scp models/production/best.pt dilger:/home/rndpig/deer-deterrent/models/production/")
    print("   scp yolov8n.pt dilger:/home/rndpig/deer-deterrent/")
    print()
    
    print("Issue 2: Missing Python Packages")
    print("   The backend needs these packages:")
    print("   - ultralytics (for YOLOv8)")
    print("   - opencv-python")
    print("   - torch/torchvision")
    print()
    print("   Install on server:")
    print("   ssh dilger")
    print("   pip install --break-system-packages ultralytics opencv-python")
    print()
    
    print("Issue 3: Import Path Problem")
    print("   The backend is in /home/rndpig/deer-deterrent/backend")
    print("   It tries to import: from src.inference.detector import DeerDetector")
    print("   This requires src/ to be in parent directory")
    print()
    print("   Check if src/ exists:")
    print("   ssh dilger")
    print("   ls -la /home/rndpig/deer-deterrent/src/inference/detector.py")
    print()
    
    print("Issue 4: Backend Running from Wrong Directory")
    print("   The systemd service must have correct WorkingDirectory")
    print()
    print("   Check systemd service:")
    print("   ssh dilger")
    print("   sudo systemctl cat deer-backend | grep WorkingDirectory")
    print()
    print("   Should show: WorkingDirectory=/home/rndpig/deer-deterrent/backend")
    print()
    
    print("="*80)
    print("Quick Fix Commands")
    print("="*80)
    print()
    print("# 1. Check backend logs for actual error:")
    print("ssh dilger 'sudo journalctl -u deer-backend -n 50 --no-pager'")
    print()
    print("# 2. Restart backend to see initialization messages:")
    print("ssh dilger 'sudo systemctl restart deer-backend && sleep 3 && sudo journalctl -u deer-backend -n 30 --no-pager'")
    print()
    print("# 3. Check if detector.py exists:")
    print("ssh dilger 'ls -la /home/rndpig/deer-deterrent/src/inference/detector.py'")
    print()
    print("# 4. Check if model files exist:")
    print("ssh dilger 'ls -lh /home/rndpig/deer-deterrent/models/production/best.pt'")
    print()
    print("# 5. Test Python import manually:")
    print("ssh dilger 'cd /home/rndpig/deer-deterrent/backend && python3 -c \"import sys; sys.path.insert(0, \"..\"); from src.inference.detector import DeerDetector; print(DeerDetector)\"'")
    print()
    
    print("="*80)
    print("Workaround: Use ML Detector Service Instead")
    print("="*80)
    print()
    print("The backend doesn't actually need its own detector!")
    print("The deer-ml-detector container is already running detection.")
    print()
    print("You can:")
    print("1. Disable detector requirement for upload (accept frames without detection)")
    print("2. Or have backend call the ml-detector service for analysis")
    print()
    print("This would require modifying backend/main.py upload endpoint.")
    print()


if __name__ == "__main__":
    diagnose_backend()
