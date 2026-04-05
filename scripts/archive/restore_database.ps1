# Database Restore Script for Deer Deterrent Project
# Usage: .\restore_database.ps1 [backup_filename]
# Example: .\restore_database.ps1 training_20251210_194024.db

param(
    [Parameter(Mandatory=$false)]
    [string]$BackupFile
)

$backupDir = "/home/rndpig/deer-deterrent/data/backups"

# If no backup file specified, show available backups
if (-not $BackupFile) {
    Write-Host "Available backups:" -ForegroundColor Cyan
    ssh dilger "ls -lht $backupDir/training_*.db 2>/dev/null | head -20"
    Write-Host ""
    Write-Host "Usage: .\restore_database.ps1 <filename>" -ForegroundColor Yellow
    Write-Host "Example: .\restore_database.ps1 training_20251210_194024.db" -ForegroundColor Yellow
    exit 1
}

Write-Host "⚠️  WARNING: This will replace the current database!" -ForegroundColor Red
Write-Host "Backup file: $BackupFile" -ForegroundColor Yellow
$confirm = Read-Host "Type 'YES' to continue"

if ($confirm -ne 'YES') {
    Write-Host "Restore cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host "Creating safety backup of current database..." -ForegroundColor Cyan
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
ssh dilger "docker exec deer-backend cp /app/data/training.db /app/data/backups/before_restore_${timestamp}.db"

Write-Host "Restoring database from $BackupFile..." -ForegroundColor Cyan

# Copy backup from host to Docker container
ssh dilger "docker cp ${backupDir}/${BackupFile} deer-backend:/app/data/training.db"

Write-Host "✓ Database restored from: $BackupFile" -ForegroundColor Green
Write-Host "✓ Safety backup saved as: before_restore_${timestamp}.db" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  You may need to restart the backend service:" -ForegroundColor Yellow
Write-Host "   ssh dilger 'docker restart deer-backend'" -ForegroundColor Gray
