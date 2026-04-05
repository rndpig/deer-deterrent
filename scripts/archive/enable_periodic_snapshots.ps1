# =============================================================================
# Enable Periodic Snapshot Detection - Deployment Script
# =============================================================================
# This script updates the Dell server to enable automatic deer detection
# on the Side and Driveway cameras every 60 seconds
# =============================================================================

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "Enable Periodic Snapshot Detection" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

$serverIP = "192.168.7.215"

# Step 1: Update .env on Dell server
Write-Host "`n[1/4] Updating .env file on Dell server..." -ForegroundColor Yellow

$envUpdates = @"

# Periodic Snapshot Configuration (added $(Get-Date -Format 'yyyy-MM-dd'))
ENABLE_PERIODIC_SNAPSHOTS=true
PERIODIC_SNAPSHOT_INTERVAL=60
PERIODIC_SNAPSHOT_CAMERAS=10cea9e4511f,587a624d3fae
RING_LOCATION_ID=
ENABLE_IRRIGATION=false
"@

# Create temp file with env updates
$tempFile = [System.IO.Path]::GetTempFileName()
$envUpdates | Out-File -FilePath $tempFile -Encoding UTF8

# Copy to server (will append to .env)
Write-Host "Copying environment updates to server..." -ForegroundColor Gray
scp $tempFile rndpi@${serverIP}:/tmp/env_updates.txt

# SSH to append to .env file
Write-Host "Appending to .env file..." -ForegroundColor Gray
ssh rndpi@$serverIP "cat /tmp/env_updates.txt >> ~/deer-deterrent/.env && rm /tmp/env_updates.txt"

# Clean up local temp file
Remove-Item $tempFile

Write-Host "✓ .env file updated" -ForegroundColor Green

# Step 2: Rebuild coordinator container
Write-Host "`n[2/4] Rebuilding coordinator container..." -ForegroundColor Yellow
ssh rndpi@$serverIP "cd ~/deer-deterrent && docker compose build coordinator"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Coordinator container rebuilt" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to rebuild coordinator" -ForegroundColor Red
    exit 1
}

# Step 3: Restart coordinator
Write-Host "`n[3/4] Restarting coordinator..." -ForegroundColor Yellow
ssh rndpi@$serverIP "cd ~/deer-deterrent && docker compose restart coordinator"

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Coordinator restarted" -ForegroundColor Green
} else {
    Write-Host "✗ Failed to restart coordinator" -ForegroundColor Red
    exit 1
}

# Step 4: Check logs
Write-Host "`n[4/4] Checking coordinator logs..." -ForegroundColor Yellow
Write-Host "Looking for periodic snapshot confirmation..." -ForegroundColor Gray
Start-Sleep -Seconds 5

ssh rndpi@$serverIP "docker logs deer-coordinator --tail 30"

Write-Host "`n=================================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Cyan

Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "1. Monitor logs: ssh rndpi@$serverIP 'docker logs -f deer-coordinator'" -ForegroundColor Gray
Write-Host "2. Look for: 'Periodic snapshots enabled' and 'Requested periodic snapshot'" -ForegroundColor Gray
Write-Host "3. Wait 1-2 minutes, then check dashboard for new detections" -ForegroundColor Gray
Write-Host ""
Write-Host "Cameras configured:" -ForegroundColor Yellow
Write-Host "  - Side Camera (10cea9e4511f)" -ForegroundColor Gray
Write-Host "  - Driveway Camera (587a624d3fae)" -ForegroundColor Gray
Write-Host "  - Snapshot interval: 60 seconds" -ForegroundColor Gray
