# Database Backup Script for Deer Deterrent Project
# Usage: .\backup_database.ps1

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = "/home/rndpig/deer-deterrent/data/backups"
$backupFile = "training_${timestamp}.db"

Write-Host "Creating database backup..." -ForegroundColor Cyan

# Create backup directories
ssh dilger "mkdir -p $backupDir"
ssh dilger "docker exec deer-backend mkdir -p /app/data/backups"

# Create backup inside Docker container
ssh dilger "docker exec deer-backend cp /app/data/training.db /app/data/backups/$backupFile"

# Copy backup to host
ssh dilger "docker cp deer-backend:/app/data/backups/$backupFile ${backupDir}/$backupFile"

Write-Host "✓ Database backed up to: ${backupDir}/$backupFile" -ForegroundColor Green

# Clean up old backups (keep last 20)
Write-Host "Cleaning old backups..." -ForegroundColor Cyan
ssh dilger "cd $backupDir && ls -t training_*.db 2>/dev/null | tail -n +21 | xargs -r rm && echo 'Kept last 20 backups'"

Write-Host "✓ Backup complete!" -ForegroundColor Green
