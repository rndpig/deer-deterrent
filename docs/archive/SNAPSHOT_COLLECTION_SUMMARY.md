# Snapshot Collection & Testing - Implementation Summary

## What Was Changed

### 1. Coordinator (Dockerfile.coordinator)
- **Added snapshot saving** - Every motion event now saves snapshot to `data/ring_snapshots/`
- **Filename format**: `event_YYYYMMDD_HHMMSS_{camera_id}_snapshot.jpg`
- **Database tracking** - Snapshot paths logged with `snapshot_path` column

### 2. Database Schema (backend/database.py)
- **Added column**: `snapshot_path TEXT` to `ring_events` table
- **Updated functions**: `log_ring_event()` now accepts `snapshot_path` parameter

### 3. Backend API (backend/main.py)
- **Updated endpoint**: `/api/ring-events` now accepts `snapshot_path` in request

### 4. New Scripts

#### migrate_snapshot_path.py
Adds `snapshot_path` column to existing databases. Run once:
```bash
python migrate_snapshot_path.py
```

#### test_snapshot_detection.py
Tests model performance on saved snapshots:
```bash
# After 24-48 hours of collection:
python test_snapshot_detection.py

# Test specific snapshot:
python test_snapshot_detection.py --test-file data/ring_snapshots/event_20260118_105030_front_yard_snapshot.jpg

# Custom threshold:
python test_snapshot_detection.py --threshold 0.20
```

## Next Steps

### Immediate (Today)
1. **Run migration**:
   ```bash
   python migrate_snapshot_path.py
   ```

2. **Restart coordinator** (if running as Docker):
   ```bash
   docker-compose restart coordinator
   ```
   Or if running as service:
   ```bash
   sudo systemctl restart deer-coordinator
   ```

3. **Verify snapshot directory**:
   ```bash
   ls -lh data/ring_snapshots/
   ```

### Collection Period (24-48 hours)
- System will automatically save snapshots with each motion event
- Target: 20-50 snapshots minimum for meaningful testing
- Mix of day/night, with/without deer

### Testing (Day 3)
1. **Run snapshot test**:
   ```bash
   python test_snapshot_detection.py
   ```

2. **Review report**:
   - Detection rate on snapshots
   - Confidence scores comparison
   - Optimal threshold determination
   - Model performance assessment

3. **Make decision**:
   - ✓ If model works → Implement burst approach
   - ⚠️ If struggling → Retrain with snapshot data
   - 📊 If mixed → Adjust thresholds per source

## Expected Results

### Scenario 1: Model Works on Snapshots ✓
```
Detection rate: 70-90%
Average confidence: 0.25-0.40
Recommendation: Proceed with burst approach
```

### Scenario 2: Model Struggles
```
Detection rate: 0-30%
Average confidence: 0.10-0.20
Recommendation: Retrain model with snapshot images
```

### Scenario 3: Mixed Performance
```
Detection rate: 30-70%
Average confidence: 0.20-0.30
Recommendation: Lower threshold OR add snapshot training data
```

## Files Modified

```
Dockerfile.coordinator          - Save snapshots to disk
backend/database.py             - Add snapshot_path column
backend/main.py                 - Accept snapshot_path in API
migrate_snapshot_path.py        - NEW: Database migration
test_snapshot_detection.py      - NEW: Model testing script
```

## Storage Requirements

- ~24KB per snapshot
- ~50 snapshots over 48 hours = ~1.2 MB
- Negligible storage impact

## Important Notes

1. **Snapshots are instant MQTT snapshots** - Same images currently sent to ML detector, now also saved to disk

2. **No impact on existing detection** - System continues to work exactly as before, just saves extra copy

3. **Coordinator must be running** - Snapshots only saved when motion events occur

4. **Test requires data** - Can't test until snapshots are collected (24-48 hours)

5. **This answers your question** - "Will my model work on snapshot images?" We'll know in 2-3 days!

## Troubleshooting

### No snapshots being saved?
```bash
# Check coordinator logs
docker logs deer-coordinator | grep "Saved snapshot"

# Should see:
# ✓ Saved snapshot to data/ring_snapshots/event_20260118_105030_front_yard_snapshot.jpg
```

### Migration fails?
```bash
# Check if column already exists
sqlite3 data/training.db "PRAGMA table_info(ring_events);" | grep snapshot_path
```

### Test script errors?
```bash
# Verify model file exists
ls -lh models/production/best.pt

# Verify snapshots collected
ls data/ring_snapshots/ | wc -l
```

## Next Implementation Phase

After testing confirms model performance on snapshots:
- Implement burst snapshot logic (3 snapshots per event)
- Add video confirmation background task
- Update thresholds based on test results
- Deploy full dual-phase detection system

See [RING_MOTION_DETECTION_PIPELINE.md](RING_MOTION_DETECTION_PIPELINE.md) for complete implementation plan.
