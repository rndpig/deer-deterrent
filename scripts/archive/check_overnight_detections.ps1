# =============================================================================
# Deer Deterrent System - Morning Check Script
# Run this in the morning to see if deer were detected overnight
# =============================================================================

Write-Host "`n=== DEER DETERRENT OVERNIGHT REPORT ===" -ForegroundColor Cyan
Write-Host "Checking system from 10pm to 6am..." -ForegroundColor Gray

# Container status
Write-Host "`n1. Container Status:" -ForegroundColor Yellow
ssh dilger-server "docker ps --filter 'name=deer-' --format 'table {{.Names}}\t{{.Status}}'"

# System configuration
Write-Host "`n2. System Configuration:" -ForegroundColor Yellow
ssh dilger-server "docker exec deer-coordinator curl -s http://localhost:5000/health | python3 -m json.tool"

# Check for motion events processed
Write-Host "`n3. Motion Events Processed (last 24 hours):" -ForegroundColor Yellow
ssh dilger-server "docker logs deer-coordinator --since 24h | grep -i 'INSTANT motion\|Processing queued event\|Detection result' | tail -20"

# Check database for detections (excluding manual uploads)
Write-Host "`n4. Live Detections in Database:" -ForegroundColor Yellow
ssh dilger-server "docker exec deer-db psql -U deeruser -d deer_deterrent -c \"SELECT COUNT(*) as live_detections FROM detections WHERE camera_name != 'Manual Upload' AND timestamp > NOW() - INTERVAL '24 hours';\" 2>/dev/null || echo 'Database query failed - backend may need restart'"

# Check for deer detections specifically
Write-Host "`n5. Deer Detections (if any):" -ForegroundColor Yellow
ssh dilger-server "docker logs deer-coordinator --since 24h | grep -i 'deer=true' | tail -10"

# Check irrigation activations
Write-Host "`n6. Irrigation Activations:" -ForegroundColor Yellow
ssh dilger-server "docker logs deer-coordinator --since 24h | grep -i 'DEER DETERRENT ACTIVATED' | tail -10"

# Check snapshot directory for saved images
Write-Host "`n7. Snapshots Saved (last 24 hours):" -ForegroundColor Yellow
ssh dilger-server "find /home/dilger/deer-deterrent/dell-deployment/data/snapshots -name '*.jpg' -mtime -1 -ls 2>/dev/null | wc -l" 2>&1

Write-Host "`n=== END OF REPORT ===" -ForegroundColor Cyan
Write-Host "`nIf you see 'INSTANT motion detected' and 'deer=true', the system is working!" -ForegroundColor Green
Write-Host "If you only see recording URLs, motion events may not be triggering properly." -ForegroundColor Yellow
