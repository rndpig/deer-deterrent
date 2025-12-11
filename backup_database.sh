#!/bin/bash
# Backup the training database before making changes

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/rndpig/deer-deterrent/data/backups"
DB_PATH="/home/rndpig/deer-deterrent/data/training.db"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Create backup
BACKUP_FILE="$BACKUP_DIR/training_${TIMESTAMP}.db"
docker exec deer-backend cp /app/data/training.db "/app/data/backups/training_${TIMESTAMP}.db"

# Also copy to host
docker cp "deer-backend:/app/data/backups/training_${TIMESTAMP}.db" "$BACKUP_FILE"

echo "✓ Database backed up to: $BACKUP_FILE"

# Keep only last 20 backups
cd "$BACKUP_DIR"
ls -t training_*.db | tail -n +21 | xargs -r rm

echo "✓ Old backups cleaned (keeping last 20)"
