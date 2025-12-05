# ============================================================================
# Dell Server Deployment Script
# Deer Deterrent System
# ============================================================================
# This script deploys the latest code to your Dell OptiPlex server
# Usage: .\deploy.ps1
# ============================================================================

param(
    [string]$ServerIP = "192.168.7.200",
    [string]$ServerUser = "rndpig",
    [string]$ProjectPath = "/home/rndpig/deer-deterrent"
)

Write-Host "🚀 Deploying Deer Deterrent System to Dell Server" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""

# Check if we can reach the server
Write-Host "1️⃣ Checking server connectivity..." -ForegroundColor Cyan
$pingResult = Test-Connection -ComputerName $ServerIP -Count 2 -Quiet
if (-not $pingResult) {
    Write-Host "❌ Cannot reach server at $ServerIP" -ForegroundColor Red
    Write-Host "   Please check that the Dell server is powered on and connected to the network." -ForegroundColor Yellow
    exit 1
}
Write-Host "✅ Server is reachable" -ForegroundColor Green
Write-Host ""

# Test SSH connection
Write-Host "2️⃣ Testing SSH connection..." -ForegroundColor Cyan
$sshTest = ssh -o ConnectTimeout=5 -o BatchMode=yes ${ServerUser}@${ServerIP} "echo 'SSH OK'" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ SSH connection failed" -ForegroundColor Red
    Write-Host "   You may need to enter your password or set up SSH keys." -ForegroundColor Yellow
    Write-Host "   Continuing anyway..." -ForegroundColor Yellow
}
else {
    Write-Host "✅ SSH connection successful" -ForegroundColor Green
}
Write-Host ""

# Pull latest changes on the server
Write-Host "3️⃣ Pulling latest code from GitHub..." -ForegroundColor Cyan
ssh ${ServerUser}@${ServerIP} "cd $ProjectPath && git pull origin main"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to pull latest code" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Code updated successfully" -ForegroundColor Green
Write-Host ""

# Rebuild and restart Docker containers
Write-Host "4️⃣ Rebuilding Docker containers..." -ForegroundColor Cyan
ssh ${ServerUser}@${ServerIP} "cd $ProjectPath && docker compose build backend"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to build backend container" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Backend container built successfully" -ForegroundColor Green
Write-Host ""

Write-Host "5️⃣ Restarting backend service..." -ForegroundColor Cyan
ssh ${ServerUser}@${ServerIP} "cd $ProjectPath && docker compose restart backend"
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to restart backend" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Backend restarted successfully" -ForegroundColor Green
Write-Host ""

# Wait a moment for service to start
Write-Host "6️⃣ Waiting for service to start..." -ForegroundColor Cyan
Start-Sleep -Seconds 5

# Check service health
Write-Host "7️⃣ Checking service health..." -ForegroundColor Cyan
$healthCheck = ssh ${ServerUser}@${ServerIP} "curl -s http://localhost:8000/health"
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Backend is healthy: $healthCheck" -ForegroundColor Green
}
else {
    Write-Host "⚠️  Health check returned unexpected result" -ForegroundColor Yellow
    Write-Host "   Checking logs..." -ForegroundColor Yellow
    ssh ${ServerUser}@${ServerIP} "cd $ProjectPath && docker compose logs --tail=20 backend"
}
Write-Host ""

# Show recent logs
Write-Host "8️⃣ Recent backend logs:" -ForegroundColor Cyan
Write-Host "------------------------------------------------" -ForegroundColor Gray
ssh ${ServerUser}@${ServerIP} "cd $ProjectPath && docker compose logs --tail=30 backend"
Write-Host "------------------------------------------------" -ForegroundColor Gray
Write-Host ""

Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📊 You can now test the API at:" -ForegroundColor Cyan
Write-Host "   http://${ServerIP}:8000/health" -ForegroundColor White
Write-Host "   http://${ServerIP}:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "📝 To view logs, run:" -ForegroundColor Cyan
Write-Host "   ssh ${ServerUser}@${ServerIP} 'cd $ProjectPath && docker compose logs -f backend'" -ForegroundColor White
Write-Host ""
