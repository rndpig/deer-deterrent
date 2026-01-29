# Remove all yolov8n.pt references and files from Dell server

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "Removing yolov8n.pt from Dell Server" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

$serverIP = "192.168.7.215"

# Step 1: Update .env on server
Write-Host "`n[1/4] Updating .env to use production model..." -ForegroundColor Yellow
ssh rndpi@$serverIP @"
cd ~/deer-deterrent
sed -i 's|YOLO_MODEL_PATH=.*yolov8n.*|YOLO_MODEL_PATH=/app/models/production/best.pt|' .env
sed -i 's|^YOLO_MODEL_PATH=/app/models/yolov8n.pt|YOLO_MODEL_PATH=/app/models/production/best.pt|' .env
echo 'Updated .env'
grep YOLO_MODEL_PATH .env
"@

Write-Host "✓ .env updated" -ForegroundColor Green

# Step 2: Find and delete yolov8n.pt files
Write-Host "`n[2/4] Finding and removing yolov8n.pt files..." -ForegroundColor Yellow
ssh rndpi@$serverIP "cd ~/deer-deterrent; find . -name 'yolov8n*.pt' -type f -delete; echo 'yolov8n.pt files deleted'"

Write-Host "checkmark yolov8n.pt files removed" -ForegroundColor Green

# Step 3: Rebuild ml-detector with production model
Write-Host "`n[3/4] Rebuilding ml-detector container..." -ForegroundColor Yellow
ssh rndpi@$serverIP "cd ~/deer-deterrent; docker compose build ml-detector"

if ($LASTEXITCODE -eq 0) {
    Write-Host "checkmark ml-detector rebuilt" -ForegroundColor Green
} else {
    Write-Host "X Failed to rebuild ml-detector" -ForegroundColor Red
    exit 1
}

# Step 4: Restart ml-detector
Write-Host "`n[4/4] Restarting ml-detector..." -ForegroundColor Yellow
ssh rndpi@$serverIP "cd ~/deer-deterrent; docker compose restart ml-detector"

if ($LASTEXITCODE -eq 0) {
    Write-Host "checkmark ml-detector restarted" -ForegroundColor Green
} else {
    Write-Host "X Failed to restart ml-detector" -ForegroundColor Red
    exit 1
}

# Verify
Write-Host "`n[Verification] Checking ML detector..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

$health = Invoke-RestMethod -Uri "http://${serverIP}:8001/health"
Write-Host "  Status: $($health.status)" -ForegroundColor $(if ($health.status -eq 'healthy') { 'Green' } else { 'Red' })
Write-Host "  Model: $($health.model_path)" -ForegroundColor $(if ($health.model_path -like '*best.pt') { 'Green' } else { 'Red' })
Write-Host "  Threshold: $($health.confidence_threshold)" -ForegroundColor Gray

Write-Host "`n=================================================" -ForegroundColor Cyan
Write-Host "yolov8n.pt Removed Successfully!" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan

Write-Host "`nML Detector now using: $($health.model_path)" -ForegroundColor Green
Write-Host "This is your custom-trained deer detection model" -ForegroundColor Gray
Write-Host ""
