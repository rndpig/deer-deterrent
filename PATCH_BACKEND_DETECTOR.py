"""
Patch for backend/main.py to use ML detector service instead of local detector.
This fixes the "Detector not initialized" error during video upload.

Instructions:
1. SSH to server: ssh dilger
2. Navigate to backend: cd /home/rndpig/deer-deterrent/backend
3. Apply this patch to main.py
4. Restart backend: sudo systemctl restart deer-backend
"""

# The fix is to modify the upload_video_for_training function to:
# 1. Remove the detector check
# 2. Use ML detector service for frame analysis
# 3. Or make detector optional

print("""
QUICK FIX OPTION 1: Make Detector Optional (Fastest)
=====================================================

Replace line 729 in backend/main.py:

FROM:
    det = load_detector()
    if not det:
        raise HTTPException(status_code=503, detail="Detector not initialized")

TO:
    det = load_detector()
    # Make detector optional - will skip detection if not available
    detector_available = det is not None
    if detector_available:
        logger.info("Detector available - will run detection on frames")
    else:
        logger.warning("Detector not available - will extract frames without detection")

Then around line 950, change:

FROM:
    # Run detection on frame
    results = det.detect(frame)
    detections = results['detections']

TO:
    # Run detection on frame (if detector available)
    if detector_available:
        results = det.detect(frame)
        detections = results['detections']
    else:
        detections = []
        logger.debug(f"Skipping detection for frame {frame_idx} (detector not available)")

This allows video upload to work without detection, you can manually annotate frames later.


QUICK FIX OPTION 2: Use ML Detector Service (Better)
====================================================

Add this helper function after load_detector() (around line 70):

async def detect_using_service(image_bytes: bytes) -> dict:
    \"\"\"Use the ML detector service instead of local detector.\"\"\"
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": ("frame.jpg", image_bytes, "image/jpeg")}
            response = await client.post(
                "http://deer-ml-detector:8001/detect",
                files=files
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"ML detector service call failed: {e}")
        return {"detections": [], "num_detections": 0}


Then in upload_video_for_training, replace detector usage (around line 950):

FROM:
    # Run detection on frame
    results = det.detect(frame)
    detections = results['detections']

TO:
    # Run detection on frame using ML detector service
    import cv2
    _, buffer = cv2.imencode('.jpg', frame)
    image_bytes = buffer.tobytes()
    results = await detect_using_service(image_bytes)
    detections = results.get('detections', [])


QUICK FIX OPTION 3: Install Dependencies on Server
==================================================

ssh dilger
pip3 install --break-system-packages ultralytics torch torchvision opencv-python
sudo systemctl restart deer-backend

This installs the required packages so the detector can initialize.
Then check logs:
sudo journalctl -u deer-backend -n 50 --no-pager


RECOMMENDED: Option 1 (Make Detector Optional)
===============================================

This is the fastest fix. Here's the complete patch:

1. SSH to server:
   ssh dilger

2. Edit the file:
   nano /home/rndpig/deer-deterrent/backend/main.py

3. Find line 729 (search for "Detector not initialized")
   
4. Change from:
   det = load_detector()
   if not det:
       raise HTTPException(status_code=503, detail="Detector not initialized")

   To:
   det = load_detector()
   detector_available = det is not None
   if not detector_available:
       logger.warning("Detector not available - frames will be extracted without auto-detection")

5. Find line ~950 (search for "det.detect(frame)")

6. Change from:
   results = det.detect(frame)
   detections = results['detections']

   To:
   if detector_available:
       results = det.detect(frame)
       detections = results['detections']
   else:
       detections = []

7. Save (Ctrl+X, Y, Enter)

8. Restart backend:
   sudo systemctl restart deer-backend

9. Test upload again from https://deer.rndpig.com

""")
