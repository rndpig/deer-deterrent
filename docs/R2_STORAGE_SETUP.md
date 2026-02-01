# Cloudflare R2 Storage Integration

## Overview

Cloudflare R2 is now integrated for:
- **Automatic backup** of all snapshots to cloud storage
- **Training dataset preservation** with metadata and bounding boxes
- **Weekly background sampling** for diverse training data

## Features Implemented

### 1. Active Hours Filtering
- Snapshots are only processed by the detector during configured active hours
- Reduces unnecessary processing and storage
- Configurable via Settings page (default: 20:00 - 06:00)
- Manual uploads can bypass this restriction

### 2. Weekly Background Sampling
- Automatically captures 1 random snapshot per camera per week
- Only during active hours (matching production conditions)
- Labeled as `weekly_background_sample` in database
- Never auto-archived (preserved for training)
- Provides seasonal variety (lighting, weather, foliage changes)

### 3. Automatic R2 Sync
- Background task syncs new snapshots every 15 minutes
- Uploads both image and metadata JSON
- Organized by year/month in bucket
- Metadata includes: event ID, camera, timestamp, deer detection, bboxes

### 4. Manual Sync Control
- API endpoint: `POST /api/storage/r2-sync`
- Trigger immediate sync of recent snapshots
- Useful for backfilling or testing

## Setup Instructions

### Step 1: Create R2 Bucket

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com)
2. Navigate to **R2 Object Storage**
3. Click **Create Bucket**
4. Name: `deer-deterrent-backup`
5. Location: Automatic
6. Click **Create Bucket**

### Step 2: Generate API Token

1. In R2 overview, click **Manage R2 API Tokens**
2. Click **Create API Token**
3. Configuration:
   - **Token Name**: `deer-deterrent-sync`
   - **Permissions**: Object Read & Write
   - **Apply to Specific Buckets**: Select `deer-deterrent-backup`
   - **TTL**: Indefinite (or set expiration if preferred)
4. Click **Create API Token**
5. **IMPORTANT**: Copy the Access Key ID and Secret Access Key now (won't be shown again)

### Step 3: Find Account ID

1. In R2 overview page, look at the URL:
   - Format: `https://dash.cloudflare.com/<ACCOUNT_ID>/r2/overview`
   - Or check **Account ID** in the sidebar

### Step 4: Configure Server

**Option A: Environment Variables** (Recommended for Docker)

Add to `docker-compose.yml` under backend service:

```yaml
backend:
  environment:
    - R2_ACCOUNT_ID=your_account_id_here
    - R2_ACCESS_KEY_ID=your_access_key_here
    - R2_SECRET_ACCESS_KEY=your_secret_here
    - R2_BUCKET_NAME=deer-deterrent-backup
```

**Option B: .env File** (For local development)

Create `configs/.env.r2` (git-ignored):

```bash
R2_ACCOUNT_ID=your_account_id_here
R2_ACCESS_KEY_ID=your_access_key_here
R2_SECRET_ACCESS_KEY=your_secret_here
R2_BUCKET_NAME=deer-deterrent-backup
```

Load before starting backend:
```bash
source configs/.env.r2
python backend/main.py
```

### Step 5: Install boto3 Dependency

R2 uses S3-compatible API via boto3:

```bash
pip install boto3
```

Or add to `requirements.txt`:
```
boto3>=1.28.0
```

### Step 6: Restart Backend

```bash
# Docker
docker compose restart backend

# Systemd
sudo systemctl restart deer-backend

# Manual
python backend/main.py
```

Check logs for:
```
✓ R2 storage client initialized
✓ R2 sync task started
```

## R2 Bucket Structure

```
deer-deterrent-backup/
├── snapshots/
│   ├── 2026/
│   │   ├── 01/
│   │   │   ├── event_20260115_083022_side.jpg
│   │   │   ├── event_20260115_083022_side.json
│   │   │   ├── event_20260115_210445_driveway.jpg
│   │   │   └── event_20260115_210445_driveway.json
│   │   └── 02/
│   │       └── ...
│   └── 2027/
│       └── ...
├── database-exports/
│   ├── training_db_20260201_120000.json
│   └── training_db_20260208_120000.json
└── training-datasets/
    ├── v1.0_baseline/
    ├── v1.1_pseudolabels/
    └── v2.0_production/
```

## Metadata JSON Format

Each snapshot has a companion `.json` file:

```json
{
  "id": 12345,
  "camera_id": "10cea9e4511f",
  "event_type": "motion",
  "timestamp": "2026-01-15T08:30:22",
  "deer_detected": 1,
  "detection_confidence": 0.87,
  "detection_bboxes": [
    {
      "confidence": 0.87,
      "bbox": [0.45, 0.32, 0.58, 0.51]
    }
  ],
  "snapshot_path": "data/snapshots/event_20260115_083022_side.jpg",
  "snapshot_size": 24576,
  "archived": 0
}
```

## API Endpoints

### Check Active Hours Status
```bash
GET /api/settings/active-hours-status

Response:
{
  "is_active_hours": true,
  "current_time": "2026-02-01T22:30:00",
  "settings": {
    "enabled": true,
    "start_hour": 20,
    "end_hour": 6
  }
}
```

### Manual R2 Sync
```bash
POST /api/storage/r2-sync?hours=24&limit=100

Response:
{
  "success": true,
  "message": "Synced 47 snapshots to R2",
  "results": {
    "uploaded": 47,
    "failed": 0,
    "skipped": 3
  }
}
```

## Cost Estimates

### Storage Costs
- **Free Tier**: 10 GB storage
- **Estimated Usage**: 
  - Images: ~24KB per snapshot
  - 30 snapshots/day (with active hours filtering) × 365 days = ~263 MB/year
  - 5 years of data = ~1.3 GB
  - **Cost**: FREE (well within 10GB limit)

### Bandwidth Costs
- **Free**: Unlimited downloads (R2's key advantage over S3)
- Perfect for downloading training datasets

### Request Costs
- **Class A** (writes): $4.50 per million requests
- **Class B** (reads): $0.36 per million requests
- Estimated: 30 uploads/day = ~11K/year = **$0.05/year**

**Total Annual Cost: ~$0 (within free tier)**

## Monitoring

### Check Sync Status

View backend logs:
```bash
# Docker
docker compose logs -f backend | grep R2

# Systemd
sudo journalctl -u deer-backend -f | grep R2

# Output examples:
# R2 sync: uploaded=12, failed=0, skipped=0
# Synced snapshot 12345 to R2
```

### View R2 Contents

1. Cloudflare Dashboard > R2 > deer-deterrent-backup
2. Browse folders
3. Download files directly from dashboard

Or use boto3 script:
```python
from src.services.r2_sync import get_r2_client

client = get_r2_client()
objects = client.list_objects(prefix='snapshots/2026/02/')
for obj in objects:
    print(f"{obj['key']}: {obj['size']} bytes")
```

## Benefits

### For Backup
- ✅ Off-site redundancy (protects against hardware failure)
- ✅ Automatic sync (no manual intervention)
- ✅ Versioned storage (R2 supports versioning)
- ✅ Durable (11 nines of durability)

### For Training
- ✅ Preserves all detections with metadata
- ✅ Easy dataset export (download from R2)
- ✅ Seasonal variety (weekly background samples)
- ✅ Negative examples preserved (deer=0 snapshots)
- ✅ Accessible from any machine (no need to SSH to server)

## Troubleshooting

### R2 not syncing
**Check credentials:**
```bash
# On server
echo $R2_ACCOUNT_ID
echo $R2_ACCESS_KEY_ID
```

**Check logs:**
```bash
docker compose logs backend | grep "R2 storage"
# Should see: "✓ R2 storage client initialized"
```

### Upload failures
**Check bucket permissions:**
- Ensure API token has Object Read & Write
- Verify token is applied to correct bucket

**Check network:**
```bash
# Test R2 endpoint
curl https://<ACCOUNT_ID>.r2.cloudflarestorage.com
```

### Boto3 not installed
```bash
pip install boto3
# Or in Docker:
docker compose exec backend pip install boto3
docker compose restart backend
```

## Next Steps

1. Set up R2 credentials (Steps 1-4 above)
2. Install boto3 and restart backend
3. Verify sync is working in logs
4. Test manual sync endpoint
5. Browse R2 bucket to see uploaded snapshots
6. Adjust active hours in Settings if needed
7. Monitor weekly background samples

## Future Enhancements

- [ ] Add `synced_to_r2` column to database to track sync status
- [ ] Implement incremental sync (only upload new snapshots)
- [ ] Add database export to R2 (daily/weekly backups)
- [ ] Create training dataset export script (downloads from R2)
- [ ] Add R2 metrics to dashboard (storage used, files synced)
- [ ] Implement R2 lifecycle policies (archive old snapshots to Glacier)
