# Snapshot Viewer Deployment Checklist

## Prerequisites Verification
- [x] Backend API endpoints implemented (`/api/ring-snapshots`)
- [x] Database migration for `snapshot_path` column completed
- [x] Coordinator modified to save snapshots to disk
- [x] Frontend snapshot viewer component created

## Deployment Steps

### 1. Deploy Frontend to Vercel
```bash
# Commit and push changes
cd "c:\Users\rndpi\Documents\Coding Projects\deer-deterrent"
git add frontend/src/components/SnapshotViewer.jsx
git add frontend/src/components/SnapshotViewer.css
git add frontend/src/components/Training.jsx
git add frontend/src/components/VideoLibrary.jsx
git add frontend/src/components/VideoLibrary.css
git add frontend/src/components/Training.css
git add docs/SNAPSHOT_VIEWER_IMPLEMENTATION.md
git add docs/SNAPSHOT_VIEWER_DEPLOYMENT.md
git commit -m "Add snapshot viewer to Model Development tab for testing ML performance on Ring snapshots"
git push origin main
```

**Expected Result**: Vercel auto-deploys within 1-2 minutes. Check deer.rndpig.com.

### 2. Restart Backend (if not already done)
```bash
# SSH to Dilger server
ssh username@dilger-server

# Restart backend container to load new API endpoints
cd /path/to/deer-deterrent
docker-compose restart backend

# Verify backend is running
docker ps | grep backend
docker logs backend --tail 50
```

**Expected Result**: Backend logs show "Uvicorn running on http://0.0.0.0:8000"

### 3. Restart Coordinator (if not already done)
```bash
# Still on Dilger server
docker-compose restart coordinator

# Verify coordinator is running
docker ps | grep coordinator
docker logs coordinator --tail 50
```

**Expected Result**: Coordinator logs show "Listening for Ring motion events..."

### 4. Verify Snapshot Directory
```bash
# Still on Dilger server
ls -la data/ring_snapshots/
```

**Expected Result**: Directory exists (may be empty until first motion event)

### 5. Test Frontend Deployment
1. Visit https://deer.rndpig.com
2. Login with credentials
3. Navigate to "Model Improvement" tab
4. Look for "📸 View Snapshots" button (orange, before "Upload Video")
5. Click button
6. Should see "No Snapshots Found" message (normal if no motion events yet)

**Expected Result**: Snapshot viewer loads without errors

### 6. Trigger Test Motion Event
1. Wave at a Ring camera to trigger motion event
2. Wait 15-20 seconds for processing
3. Click "🔄 Reload" button in snapshot viewer
4. Should see snapshot appear in grid

**Expected Result**: Snapshot thumbnail appears with camera name, timestamp, file size

### 7. Test Detail View
1. Click on snapshot thumbnail
2. Should see full-size image in detail panel
3. Verify metadata displays correctly:
   - Event ID
   - Camera name
   - Timestamp (formatted)
   - Deer detected status
   - Confidence score (if detected)
   - File size

**Expected Result**: Detail panel shows all metadata correctly

### 8. Test Re-run Detection
1. With snapshot selected in detail view
2. Adjust confidence threshold slider (try 0.20)
3. Click "🔍 Run Detection" button
4. Wait for response (should be quick, <2 seconds)
5. Should see alert with results
6. If deer detected, bounding boxes should appear on image

**Expected Result**: Detection runs successfully and results update

## Verification Checklist
- [ ] Frontend deployed to Vercel (check build status)
- [ ] Backend restarted and running
- [ ] Coordinator restarted and running
- [ ] Snapshot directory exists (`data/ring_snapshots/`)
- [ ] Can access snapshot viewer in web app
- [ ] "View Snapshots" button appears in Video Library
- [ ] Test motion event generates snapshot
- [ ] Snapshot appears in viewer grid
- [ ] Can click snapshot to view details
- [ ] Can re-run detection with different threshold
- [ ] No console errors in browser

## Troubleshooting

### Frontend Not Updated
**Issue**: "View Snapshots" button doesn't appear

**Solutions**:
1. Check Vercel build status: https://vercel.com/dashboard
2. Force refresh browser (Ctrl+Shift+R)
3. Check browser console for errors (F12)
4. Verify git push succeeded: `git log --oneline -n 5`

### Backend Endpoints Not Working
**Issue**: "Failed to load snapshots" error

**Solutions**:
1. Check backend logs: `docker logs backend`
2. Verify backend is running: `docker ps | grep backend`
3. Test endpoint directly: `curl https://deer-api.rndpig.com/api/ring-snapshots`
4. Check CORS settings if browser blocks request

### Coordinator Not Saving Snapshots
**Issue**: Directory exists but no snapshots appear

**Solutions**:
1. Check coordinator logs: `docker logs coordinator --tail 100`
2. Trigger motion event and watch logs in real-time: `docker logs -f coordinator`
3. Verify Ring-MQTT is publishing snapshots: `mosquitto_sub -t 'ring/+/motion/#'`
4. Check file permissions: `ls -la data/ring_snapshots/`
5. Verify coordinator Dockerfile.coordinator lines 455-485 are present

### Images Not Loading
**Issue**: Snapshot thumbnails show broken image icon

**Solutions**:
1. Check backend logs for 404 errors
2. Verify snapshot files exist: `ls data/ring_snapshots/`
3. Test image endpoint: `curl https://deer-api.rndpig.com/api/ring-snapshots/5584/image`
4. Check snapshot_path in database: `sqlite3 data/training.db "SELECT id, snapshot_path FROM ring_events WHERE snapshot_path IS NOT NULL LIMIT 5;"`

## Post-Deployment Actions

### Immediate (Within 1 hour)
1. Monitor coordinator logs for snapshot saving
2. Verify at least 1 test snapshot appears in viewer
3. Test all viewer features (filter, detail view, re-run detection)
4. Document any errors in GitHub Issues

### Short Term (24-48 hours)
1. Wait for natural motion events to collect 20-50 snapshots
2. Manually review snapshots for deer presence
3. Document model performance (true/false positives/negatives)
4. Test different confidence thresholds
5. Determine if model works adequately on snapshots

### Performance Testing Results Template
Create a document: `docs/SNAPSHOT_MODEL_PERFORMANCE.md`

```markdown
# Snapshot Model Performance Test Results

## Test Period
- Start: [Date/Time]
- End: [Date/Time]
- Duration: [Hours]

## Snapshot Collection
- Total Snapshots: [Number]
- With Deer (Manual Review): [Number]
- Without Deer (Manual Review): [Number]

## Model Performance @ 0.15 Threshold
- True Positives: [Number] (Detected deer, deer present)
- False Positives: [Number] (Detected deer, no deer)
- True Negatives: [Number] (No detection, no deer)
- False Negatives: [Number] (No detection, deer present)
- Precision: [TP / (TP + FP)]
- Recall: [TP / (TP + FN)]
- Accuracy: [(TP + TN) / Total]

## Threshold Testing
| Threshold | TP | FP | TN | FN | Precision | Recall | Accuracy |
|-----------|----|----|----|----|-----------|--------|----------|
| 0.10      |    |    |    |    |           |        |          |
| 0.15      |    |    |    |    |           |        |          |
| 0.20      |    |    |    |    |           |        |          |
| 0.25      |    |    |    |    |           |        |          |
| 0.30      |    |    |    |    |           |        |          |

## Observations
- [Note any patterns, common failure modes, etc.]

## Recommendation
- [ ] Proceed with burst snapshot approach (snapshots work well)
- [ ] Keep video processing (snapshots unreliable)
- [ ] Need more data to decide
- [ ] Consider retraining model with snapshot images

## Next Steps
- [Action items based on results]
```

## Success Criteria
- ✅ Frontend deploys without build errors
- ✅ Backend endpoints return 200 status
- ✅ Snapshot viewer loads in browser
- ✅ At least 1 test snapshot appears after motion event
- ✅ Can view snapshot details and metadata
- ✅ Can re-run detection with different thresholds
- ✅ No critical errors in logs or console

## Rollback Plan (If Needed)
If deployment causes critical issues:

```bash
# Revert frontend changes
git revert HEAD
git push origin main

# Vercel will auto-deploy previous version

# Backend/coordinator changes are backward compatible
# (new endpoints don't affect existing functionality)
# No rollback needed unless critical errors occur
```

## Notes
- Frontend changes are purely additive (no breaking changes)
- Backend endpoints were already added in previous session
- Coordinator changes were already deployed
- This deployment just adds the UI to view existing data
- Low risk deployment (new feature, doesn't modify existing features)

## Completion
- Date: [Fill in after deployment]
- Deployed By: [Name]
- Status: [ ] Success / [ ] Partial / [ ] Failed
- Notes: [Any issues encountered]
