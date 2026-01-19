"""
Check actual backend logs to see why detector initialization is failing.
"""
import requests

API_URL = "https://deer-api.rndpig.com"

def check_backend_status():
    """Get backend logs to diagnose the actual issue."""
    
    print("="*80)
    print("Checking Backend Status and Logs")
    print("="*80)
    print()
    
    print("Fetching backend initialization logs...")
    print()
    print("Commands to run on server:")
    print()
    print("# Check if backend is running and when it started:")
    print("ssh dilger 'sudo systemctl status deer-backend | head -20'")
    print()
    print("# Check recent backend logs for detector initialization:")
    print("ssh dilger 'sudo journalctl -u deer-backend --since \"1 hour ago\" --no-pager | grep -i detector'")
    print()
    print("# Check startup logs:")
    print("ssh dilger 'sudo journalctl -u deer-backend --since \"1 hour ago\" --no-pager | head -50'")
    print()
    print("# Check if model files exist:")
    print("ssh dilger 'ls -lh /home/rndpig/deer-deterrent/models/production/best.pt 2>&1'")
    print("ssh dilger 'ls -lh /home/rndpig/deer-deterrent/yolov8n.pt 2>&1'")
    print()
    print("# Check if src/inference/detector.py exists:")
    print("ssh dilger 'ls -lh /home/rndpig/deer-deterrent/src/inference/detector.py 2>&1'")
    print()
    print("# Test Python imports manually:")
    print("ssh dilger 'cd /home/rndpig/deer-deterrent/backend && python3 -c \"import sys; sys.path.insert(0, \\\"..\\\"); from src.inference.detector import DeerDetector; print(\\\"SUCCESS\\\")\"'")
    print()
    print("="*80)
    print()
    
    # Try to trigger an error to see the actual message
    print("Testing upload endpoint to see actual error...")
    try:
        # Create a small test file
        import io
        test_content = b"test video content"
        files = {'video': ('test.mp4', io.BytesIO(test_content), 'video/mp4')}
        
        response = requests.post(
            f"{API_URL}/api/videos/upload",
            files=files,
            data={'sample_rate': 30},
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        print()
        
        if response.status_code == 503:
            print("✓ Confirmed: Backend returns 503 - Detector not initialized")
            print()
            print("This means load_detector() is returning None.")
            print("Need to check WHY it's returning None on the server.")
        
    except Exception as e:
        print(f"Error testing endpoint: {e}")
        print()


if __name__ == "__main__":
    check_backend_status()
