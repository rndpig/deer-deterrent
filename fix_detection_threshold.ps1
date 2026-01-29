# Fix ML Detection Threshold Issue
# The ML detector was using 0.75 confidence threshold (too high)
# This changes it to 0.15 to match the manual re-detect threshold

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "Fix ML Detection Confidence Threshold" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

Write-Host "`nIssue: ML detector using 0.75 threshold, rejecting most detections" -ForegroundColor Yellow
Write-Host "Solution: Change to 0.15 threshold (same as manual re-detect)" -ForegroundColor Green

# Update the .env file
Write-Host "`n[1/2] Updating CONFIDENCE_THRESHOLD in .env..." -ForegroundColor Cyan

# Create PowerShell command to update the value
$updateCommand = @"
cd ~/deer-deterrent
if grep -q '^CONFIDENCE_THRESHOLD=' .env; then
  sed -i 's/^CONFIDENCE_THRESHOLD=.*/CONFIDENCE_THRESHOLD=0.15/' .env
  echo 'Updated existing CONFIDENCE_THRESHOLD to 0.15'
else
  echo 'CONFIDENCE_THRESHOLD=0.15' >> .env
  echo 'Added CONFIDENCE_THRESHOLD=0.15 to .env'
fi
cat .env | grep CONFIDENCE_THRESHOLD
"@

Write-Host "Connecting to Dell server..."
ssh rndpi@192.168.7.215 $updateCommand

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to update .env file" -ForegroundColor Red
    exit 1
}

Write-Host "✓ .env updated" -ForegroundColor Green

# Restart ML detector
Write-Host "`n[2/2] Restarting ML detector container..." -ForegroundColor Cyan
ssh rndpi@192.168.7.215 "cd ~/deer-deterrent && docker compose restart ml-detector"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ ML detector restarted" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to restart ML detector" -ForegroundColor Red
    exit 1
}

# Wait for it to be healthy
Write-Host "`nWaiting for ML detector to be ready..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Check the new threshold
Write-Host "`n[Verification] Checking ML detector configuration..." -ForegroundColor Cyan
$health = Invoke-RestMethod -Uri "http://192.168.7.215:8001/health"

Write-Host "  Status: $($health.status)" -ForegroundColor $(if ($health.status -eq 'healthy') { 'Green' } else { 'Red' })
Write-Host "  Confidence Threshold: $($health.confidence_threshold)" -ForegroundColor $(if ($health.confidence_threshold -eq 0.15) { 'Green' } else { 'Red' })

Write-Host "`n=================================================" -ForegroundColor Cyan
Write-Host "Fix Applied Successfully!" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan

Write-Host "`nWhat Changed:" -ForegroundColor Yellow
Write-Host "  - Confidence threshold: 0.75 → 0.15" -ForegroundColor Gray
Write-Host "  - This matches the manual re-detect threshold" -ForegroundColor Gray
Write-Host "  - Periodic snapshots will now detect deer automatically" -ForegroundColor Gray

Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "1. Wait 60 seconds for next periodic snapshot" -ForegroundColor Gray
Write-Host "2. Check dashboard for automatic deer detections" -ForegroundColor Gray
Write-Host "3. If you want to re-process existing snapshots with new threshold:" -ForegroundColor Gray
Write-Host "   Go to each 'no deer' snapshot and click Re-Detect button" -ForegroundColor Gray
Write-Host ""
