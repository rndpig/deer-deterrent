# Snapshot Viewer Implementation

## Overview
Added a snapshot viewer to the web application (Vercel deployment at deer.rndpig.com) to review Ring motion event snapshots and test ML model performance on snapshot images.

## Purpose
- **Manual Review**: View snapshots as they're collected from Ring motion events
- **Model Testing**: Validate whether the ML model (trained on video frames) works on snapshot images
- **Ground Truth Collection**: Manually identify which snapshots contain deer
- **Detection Analysis**: Review detection results, confidence scores, and bounding boxes
- **Re-run Detection**: Test different confidence thresholds on saved snapshots

## Files Modified

### Frontend Components Created
1. **frontend/src/components/SnapshotViewer.jsx** (NEW)
   - Main snapshot viewer component
   - Features:
     - Grid view of all collected snapshots
     - Filter by: All, With Deer, No Deer
     - Thumbnail view with badges (deer presence, confidence %)
     - Click to view full size with detection bounding boxes
     - Re-run detection button with adjustable threshold (0.10-0.50)
     - Metadata display (event ID, camera, timestamp, file size)
   
2. **frontend/src/components/SnapshotViewer.css** (NEW)
   - Responsive grid layout (auto-fill, min 250px columns)
   - Orange border for snapshots with deer
   - Green selection border
   - Sticky detail panel on larger screens
   - Detection bounding boxes with confidence labels

### Frontend Components Modified
3. **frontend/src/components/Training.jsx**
   - Added 'snapshots' view mode (alongside 'library', 'selector', 'review')
   - Added `handleViewSnapshots()` function to switch to snapshot view
   - Added rendering for snapshot viewer with back-to-library navigation
   - Import: `import SnapshotViewer from './SnapshotViewer'`

4. **frontend/src/components/VideoLibrary.jsx**
   - Added `onViewSnapshots` prop
   - Added "📸 View Snapshots" button to header (orange gradient)
   - Button positioned before "Upload Video" button

5. **frontend/src/components/VideoLibrary.css**
   - Added `.btn-view-snapshots` style with orange gradient (#f59e0b → #d97706)
   - Hover effect with transform and shadow

6. **frontend/src/components/Training.css**
   - Added `.snapshot-header-nav` style for back button container

## Backend API Endpoints (Already Implemented)

### GET /api/ring-snapshots
**Query Parameters:**
- `limit` (int): Max number of snapshots to return (default: 100)
- `with_deer` (bool): Filter by deer presence (true/false/omit for all)

**Response:**
```json
{
  "snapshots": [
    {
      "id": 5584,
      "timestamp": "2026-01-16T22:06:30",
      "camera_id": "Front Porch",
      "deer_detected": false,
      "detection_confidence": 0.12,
      "snapshot_path": "data/ring_snapshots/event_20260116_220630_front_porch_snapshot.jpg",
      "snapshot_size": 24576
    }
  ]
}
```

### GET /api/ring-snapshots/{event_id}/image
**Returns:** JPEG image file (FileResponse)

### POST /api/ring-snapshots/{event_id}/rerun-detection
**Query Parameters:**
- `threshold` (float): Confidence threshold (default: 0.15)

**Response:**
```json
{
  "event_id": 5584,
  "deer_detected": true,
  "max_confidence": 0.42,
  "detections": [
    {
      "confidence": 0.42,
      "bbox": {
        "x1": 120,
        "y1": 80,
        "x2": 240,
        "y2": 200
      }
    }
  ]
}
```

## User Workflow

### Access Snapshot Viewer
1. Navigate to deer.rndpig.com
2. Login with credentials
3. Go to "Model Improvement" tab (previously "Model Development")
4. Click "📸 View Snapshots" button in Video Library header

### Review Snapshots
1. **Grid View**: All snapshots displayed as thumbnails
   - Orange badge: "🦌 Deer" if detected
   - Black badge: Confidence percentage
   - Green border: Currently selected snapshot
   
2. **Filter Options**:
   - All: Show all snapshots
   - With Deer: Only show snapshots where deer was detected
   - No Deer: Only show snapshots where no deer was detected

3. **Detail View**: Click any snapshot to view full size
   - Full resolution image
   - Detection bounding boxes (orange) with confidence labels
   - Metadata panel:
     - Event ID
     - Camera name
     - Timestamp (local time format)
     - Deer detected (✓ Yes / ✗ No)
     - Confidence score
     - File size
   
4. **Re-run Detection**:
   - Adjust confidence threshold slider (0.10-0.50)
   - Click "🔍 Run Detection"
   - View updated results immediately
   - Results update in both detail view and grid view

### Manual Verification Process
1. Review snapshots as they're collected (no need to wait 48 hours)
2. Identify which snapshots actually have deer (your ground truth)
3. Compare with model's detection results
4. Test different confidence thresholds to find optimal setting
5. Document model performance on snapshots vs video frames

## Deployment

### Prerequisites
- Coordinator must be running with snapshot-saving enabled (already implemented)
- Backend API must be deployed with snapshot endpoints (already implemented)
- Snapshots stored on Dilger server at `data/ring_snapshots/`

### Deploy Frontend Changes
```bash
# From frontend/ directory
cd frontend
git add .
git commit -m "Add snapshot viewer to Model Development tab"
git push

# Vercel auto-deploys from main branch
# Should be live at deer.rndpig.com within 1-2 minutes
```

### Verify Deployment
1. Wait for Vercel build to complete
2. Visit deer.rndpig.com
3. Login and navigate to Model Improvement tab
4. Click "View Snapshots" button
5. Should see message: "No Snapshots Found" (until motion events occur)

### After First Motion Event
1. Trigger test motion event (wave at camera)
2. Wait 10-15 seconds for coordinator to process
3. Click "🔄 Reload" in snapshot viewer
4. Should see first snapshot appear in grid

## Testing Model Performance

### Collect Snapshots (24-48 hours)
- Wait for natural motion events
- Aim for 20-50 snapshots minimum
- Need mix of deer/no-deer events

### Manual Review Process
1. **Review Each Snapshot**:
   - Click to view full size
   - Note which ones actually have deer
   - Check detection results
   
2. **Document Results**:
   - True Positives: Model detected deer, deer present
   - False Positives: Model detected deer, no deer present
   - True Negatives: Model didn't detect deer, no deer present
   - False Negatives: Model didn't detect deer, deer present
   
3. **Test Thresholds**:
   - Current: 0.15 (15%)
   - Try: 0.10, 0.20, 0.25, 0.30
   - Find optimal balance of precision/recall

### Decision Points
- **If model works well on snapshots (>80% accuracy)**:
  - Proceed with burst snapshot approach (3 frames at 0.3s intervals)
  - Skip video processing for faster response time
  
- **If model struggles on snapshots (<80% accuracy)**:
  - Keep video processing as primary detection method
  - Use snapshots only for initial filtering
  - May need to retrain model with snapshot images included

## Next Steps

### Immediate (After Deployment)
1. ✅ Deploy frontend changes to Vercel
2. ✅ Verify snapshot viewer loads correctly
3. ✅ Restart backend to load new API endpoints (if not already done)
4. ✅ Restart coordinator to start saving snapshots (if not already done)
5. ✅ Trigger test motion event and verify snapshot appears

### Short Term (24-48 hours)
6. Collect 20-50 snapshots from natural motion events
7. Manually review each snapshot for deer presence
8. Document model performance metrics
9. Test different confidence thresholds
10. Determine if burst approach is viable

### Long Term (After Testing)
11. If snapshots work: Implement burst snapshot approach (3 frames)
12. If snapshots fail: Keep video processing, investigate model retraining
13. Update documentation with performance findings
14. Optimize detection pipeline based on results

## Technical Notes

### Snapshot Characteristics
- **Format**: JPEG
- **Size**: ~24KB (Ring-MQTT compressed)
- **Resolution**: Lower than video frames
- **Quality**: May have motion blur, lower light sensitivity
- **Difference from Video**: Single instant vs. multiple frames to choose from

### Model Training Context
- Model trained exclusively on video frames (30 FPS, higher quality)
- Snapshots are different image characteristics
- Performance on snapshots is unknown (reason for this viewer)

### Performance Considerations
- Snapshots load lazily (loading="lazy" attribute)
- Grid uses auto-fill responsive layout
- Detail panel is sticky on larger screens
- Re-run detection uses same ML detector as coordinator
- No file downloads required (images served via API)

## Troubleshooting

### "No Snapshots Found" Message
- **Cause**: No motion events recorded yet OR coordinator not saving snapshots
- **Solution**: 
  - Trigger test motion event
  - Verify coordinator container is running: `docker ps | grep coordinator`
  - Check coordinator logs: `docker logs coordinator`
  - Verify snapshots in: `ls data/ring_snapshots/`

### Images Not Loading
- **Cause**: Backend API unreachable OR snapshot files missing
- **Solution**:
  - Check backend logs: `docker logs backend`
  - Verify files exist: `ls data/ring_snapshots/`
  - Check VITE_API_URL environment variable in frontend

### Re-run Detection Fails
- **Cause**: ML detector not loaded OR model file missing
- **Solution**:
  - Verify model file: `ls models/production/best.pt`
  - Check backend logs for detector loading errors
  - Restart backend container

### Snapshot Path Not Recorded
- **Cause**: Coordinator not updated OR database migration not run
- **Solution**:
  - Verify coordinator code updated (lines 455-485)
  - Verify database schema: `sqlite3 data/training.db ".schema ring_events"`
  - Should see `snapshot_path TEXT` column
  - Run migration if needed: `python migrate_snapshot_path.py`

## Related Documentation
- [SNAPSHOT_COLLECTION_SUMMARY.md](SNAPSHOT_COLLECTION_SUMMARY.md) - Backend implementation details
- [RING_MOTION_DETECTION_PIPELINE.md](RING_MOTION_DETECTION_PIPELINE.md) - Pipeline design and analysis
- [check_snapshot_access.py](../check_snapshot_access.py) - Investigation of Jan 16 incident

## Summary
The snapshot viewer provides immediate visibility into Ring motion events and ML detection performance without waiting for automated testing. This enables rapid iteration on detection thresholds and validation of the burst snapshot approach before full implementation.
