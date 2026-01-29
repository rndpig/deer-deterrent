# Diagnostic script to check why periodic snapshots aren't being detected
# Run this to see what's happening

Write-Host "`n=== Checking Periodic Snapshot Configuration ===" -ForegroundColor Cyan

# Check recent snapshots
Write-Host "`n[1] Checking recent Ring snapshots in database..." -ForegroundColor Yellow
$snapshots = Invoke-RestMethod -Uri "http://192.168.7.215:8000/api/ring-snapshots?limit=20"
$total = $snapshots.snapshots.Count
$withDeer = ($snapshots.snapshots | Where-Object { $_.deer_detected -eq $true }).Count
$noDeer = ($snapshots.snapshots | Where-Object { $_.deer_detected -eq $false }).Count
$null = ($snapshots.snapshots | Where-Object { $_.deer_detected -eq $null }).Count

Write-Host "  Total snapshots: $total" -ForegroundColor Gray
Write-Host "  With deer: $withDeer" -ForegroundColor Green
Write-Host "  No deer: $noDeer" -ForegroundColor Gray  
Write-Host "  Not processed (NULL): $null" -ForegroundColor Red

if ($null -gt 0) {
    Write-Host "`n  ⚠️  Found $null snapshots that haven't been processed by ML!" -ForegroundColor Yellow
    $unprocessed = $snapshots.snapshots | Where-Object { $_.deer_detected -eq $null } | Select-Object -First 5
    Write-Host "  Sample unprocessed snapshots:" -ForegroundColor Gray
    $unprocessed | ForEach-Object {
        Write-Host "    - Event $($_.event_id): Camera $($_.camera_id) at $($_.event_time)" -ForegroundColor Gray
    }
}

# Check coordinator logs for errors
Write-Host "`n[2] Checking coordinator logs for ML detection activity..." -ForegroundColor Yellow
Write-Host "  (Looking for last 20 ML detection attempts)" -ForegroundColor Gray

try {
    $logOutput = docker logs deer-coordinator --tail 100 2>&1 | Select-String -Pattern "ML detection|periodic|deer_detected|Processing camera event" | Select-Object -Last 20
    
    if ($logOutput) {
        $logOutput | ForEach-Object { 
            $line = $_.Line
            if ($line -match "deer_detected") {
                Write-Host "  $line" -ForegroundColor Green
            } elseif ($line -match "periodic") {
                Write-Host "  $line" -ForegroundColor Cyan
            } else {
                Write-Host "  $line" -ForegroundColor Gray
            }
        }
    } else {
        Write-Host "  ⚠️  No ML detection activity found in recent logs!" -ForegroundColor Red
    }
} catch {
    Write-Host "  ⚠️  Could not access coordinator logs (not running in Docker context)" -ForegroundColor Yellow
    Write-Host "  Run this command manually: docker logs deer-coordinator --tail 100" -ForegroundColor Gray
}

# Check if periodic snapshots are enabled
Write-Host "`n[3] Checking coordinator configuration..." -ForegroundColor Yellow
try {
    $envVars = docker inspect deer-coordinator --format='{{range .Config.Env}}{{println .}}{{end}}' | Select-String -Pattern "PERIODIC|ENABLE"
    
    Write-Host "  Environment variables:" -ForegroundColor Gray
    $envVars | ForEach-Object { 
        $line = $_.Line
        if ($line -match "ENABLE_PERIODIC_SNAPSHOTS=true") {
            Write-Host "  ✓ $line" -ForegroundColor Green
        } elseif ($line -match "ENABLE_PERIODIC_SNAPSHOTS") {
            Write-Host "  ✗ $line" -ForegroundColor Red
        } else {
            Write-Host "    $line" -ForegroundColor Gray
        }
    }
} catch {
    Write-Host "  ⚠️  Could not inspect coordinator container" -ForegroundColor Yellow
}

Write-Host "`n=== Diagnosis Complete ===" -ForegroundColor Cyan
Write-Host "`nPossible Issues:" -ForegroundColor Yellow
Write-Host "1. If NULL detection count > 0: Snapshots exist but ML detection not running" -ForegroundColor Gray
Write-Host "2. If ENABLE_PERIODIC_SNAPSHOTS=false: Need to enable in .env and restart" -ForegroundColor Gray
Write-Host "3. If no periodic logs: Poller might not be running" -ForegroundColor Gray
Write-Host ""
