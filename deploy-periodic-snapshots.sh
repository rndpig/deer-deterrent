#!/bin/bash
# =============================================================================
# Deploy Periodic Snapshot Polling Feature
# =============================================================================
# This script deploys the coordinator with periodic snapshot polling enabled
# for the Side camera (10cea9e4511f)
#
# Usage:
#   ./deploy-periodic-snapshots.sh
# =============================================================================

set -e  # Exit on error

echo "========================================"
echo "Deer Deterrent - Periodic Snapshots"
echo "Deploying coordinator updates..."
echo "========================================"
echo ""

# Set environment variables for periodic snapshots
export ENABLE_PERIODIC_SNAPSHOTS=true
export PERIODIC_SNAPSHOT_INTERVAL=60  # 1 minute
export PERIODIC_SNAPSHOT_CAMERAS=10cea9e4511f  # Side camera only
export RING_LOCATION_ID=""  # Auto-detected from MQTT topics

echo "Configuration:"
echo "  ENABLE_PERIODIC_SNAPSHOTS=$ENABLE_PERIODIC_SNAPSHOTS"
echo "  PERIODIC_SNAPSHOT_INTERVAL=$PERIODIC_SNAPSHOT_INTERVAL seconds"
echo "  PERIODIC_SNAPSHOT_CAMERAS=$PERIODIC_SNAPSHOT_CAMERAS"
echo ""

# Rebuild coordinator with new code
echo "Step 1: Rebuilding coordinator image..."
docker compose build coordinator

# Stop old coordinator
echo ""
echo "Step 2: Stopping old coordinator..."
docker compose stop coordinator

# Start new coordinator
echo ""
echo "Step 3: Starting new coordinator..."
docker compose up -d coordinator

# Wait for startup
echo ""
echo "Step 4: Waiting for startup (15 seconds)..."
sleep 15

# Check health
echo ""
echo "Step 5: Checking coordinator health..."
docker compose ps coordinator
echo ""
docker compose logs --tail 50 coordinator

echo ""
echo "========================================"
echo "Deployment Complete!"
echo "========================================"
echo ""
echo "Monitoring commands:"
echo "  docker compose logs -f coordinator                # Follow logs"
echo "  docker compose logs coordinator | grep 'periodic' # Check periodic snapshots"
echo "  docker compose logs coordinator | grep 'deer'     # Check detections"
echo ""
echo "Configuration can be changed in docker-compose.yml environment variables:"
echo "  ENABLE_PERIODIC_SNAPSHOTS  - true/false"
echo "  PERIODIC_SNAPSHOT_INTERVAL - Seconds between snapshots (default: 60)"
echo "  PERIODIC_SNAPSHOT_CAMERAS  - Comma-separated camera IDs"
echo ""
echo "Expected behavior:"
echo "  - Every 60 seconds: 'Requested periodic snapshot from camera 10cea9e4511f'"
echo "  - 2 seconds later: 'Logged periodic snapshot event #XXXX'"
echo "  - If deer detected: 'ML detection: X objects, deer=True'"
echo "  - If irrigation activated: '✓✓✓ DEER DETERRENT ACTIVATED ✓✓✓'"
echo ""
echo "Note: RING_LOCATION_ID will be auto-detected from MQTT topics"
echo "      (visible in logs as 'Detected Ring location ID: XXXXX')"
echo ""
