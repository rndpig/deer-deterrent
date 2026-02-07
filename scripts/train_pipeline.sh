#!/usr/bin/env bash
# =============================================================================
# Deer Detector Training Pipeline v2.0
# =============================================================================
# One-command end-to-end pipeline: export → train → deploy
#
# Run in tmux so it survives SSH disconnection:
#   tmux new -s train
#   cd /home/rndpig/deer-deterrent
#   bash scripts/train_pipeline.sh
#   # Ctrl+B, D to detach
#   # tmux attach -t train to reconnect
#
# Options:
#   --export-only    Only run the export step
#   --skip-export    Skip export, use latest existing dataset
#   --skip-deploy    Train only, don't deploy to production
#   --epochs N       Override epoch count (default 150)
#   --batch N        Override batch size (default 8)
# =============================================================================

set -euo pipefail

PROJECT_ROOT="/home/rndpig/deer-deterrent"
SCRIPTS_DIR="${PROJECT_ROOT}/scripts"
DATASETS_DIR="${PROJECT_ROOT}/data/training_datasets"
RUNS_DIR="${PROJECT_ROOT}/runs/train"
MODELS_DIR="${PROJECT_ROOT}/dell-deployment/models"
PRODUCTION_MODEL="${MODELS_DIR}/production/best.pt"
LOG_FILE="${PROJECT_ROOT}/logs/train_pipeline_$(date +%Y%m%d_%H%M%S).log"

# Defaults
SKIP_EXPORT=false
EXPORT_ONLY=false
SKIP_DEPLOY=false
EPOCHS=150
BATCH=8
DEVICE="cpu"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --export-only) EXPORT_ONLY=true; shift ;;
        --skip-export) SKIP_EXPORT=true; shift ;;
        --skip-deploy) SKIP_DEPLOY=true; shift ;;
        --epochs) EPOCHS="$2"; shift 2 ;;
        --batch) BATCH="$2"; shift 2 ;;
        --device) DEVICE="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Setup
mkdir -p "$(dirname "$LOG_FILE")" "$RUNS_DIR" "$DATASETS_DIR"

# Tee output to both console and log file
exec > >(tee -a "$LOG_FILE") 2>&1

echo "============================================================================="
echo "  DEER DETECTOR TRAINING PIPELINE v2.0"
echo "============================================================================="
echo "  Started:      $(date)"
echo "  Project:      ${PROJECT_ROOT}"
echo "  Skip export:  ${SKIP_EXPORT}"
echo "  Skip deploy:  ${SKIP_DEPLOY}"
echo "  Epochs:       ${EPOCHS}"
echo "  Batch:        ${BATCH}"
echo "  Device:       ${DEVICE}"
echo "  Log:          ${LOG_FILE}"
echo "============================================================================="
echo ""

# =============================================================================
# STEP 1: Export dataset
# =============================================================================
DATASET_DIR=""

if [ "$SKIP_EXPORT" = true ]; then
    # Find the latest existing dataset
    DATASET_DIR=$(ls -dt "${DATASETS_DIR}"/v2.0_* 2>/dev/null | head -1 || true)
    if [ -z "$DATASET_DIR" ] || [ ! -f "${DATASET_DIR}/data.yaml" ]; then
        echo "ERROR: No existing dataset found in ${DATASETS_DIR}"
        echo "Run without --skip-export to create one."
        exit 1
    fi
    echo "Using existing dataset: ${DATASET_DIR}"
else
    echo "============================================================================="
    echo "  STEP 1: Exporting dataset with CLAHE preprocessing"
    echo "============================================================================="
    echo ""
    
    cd "${PROJECT_ROOT}"
    python3 "${SCRIPTS_DIR}/export_dataset_v2.py"
    
    # Find the dataset that was just created (most recent)
    DATASET_DIR=$(ls -dt "${DATASETS_DIR}"/v2.0_* 2>/dev/null | head -1)
    
    if [ -z "$DATASET_DIR" ] || [ ! -f "${DATASET_DIR}/data.yaml" ]; then
        echo "ERROR: Export failed — no data.yaml found"
        exit 1
    fi
    
    echo ""
    echo "  Dataset exported to: ${DATASET_DIR}"
    echo ""
    
    if [ "$EXPORT_ONLY" = true ]; then
        echo "  Export-only mode. Stopping here."
        echo "  To train: bash scripts/train_pipeline.sh --skip-export"
        exit 0
    fi
fi

DATA_YAML="${DATASET_DIR}/data.yaml"
echo "  data.yaml: ${DATA_YAML}"

# Print dataset stats
echo ""
echo "  Dataset contents:"
for split in train val test; do
    if [ -d "${DATASET_DIR}/images/${split}" ]; then
        count=$(ls "${DATASET_DIR}/images/${split}" 2>/dev/null | wc -l)
        echo "    ${split}: ${count} images"
    fi
done
echo ""

# =============================================================================
# STEP 2: Train YOLO26s
# =============================================================================
echo "============================================================================="
echo "  STEP 2: Training YOLO26s (${EPOCHS} epochs, batch=${BATCH}, device=${DEVICE})"
echo "  This will take a long time on CPU (~30-50 hours). Go do something else."
echo "============================================================================="
echo ""

cd "${PROJECT_ROOT}"
python3 "${SCRIPTS_DIR}/train_yolo26s_v2.py" \
    --data "${DATA_YAML}" \
    --output "${RUNS_DIR}" \
    --epochs "${EPOCHS}" \
    --batch "${BATCH}" \
    --device "${DEVICE}"

# Find the best model from the latest run
LATEST_RUN=$(ls -dt "${RUNS_DIR}"/deer_v2_*_phase2 2>/dev/null | head -1 || true)
if [ -z "$LATEST_RUN" ]; then
    LATEST_RUN=$(ls -dt "${RUNS_DIR}"/deer_v2_*_phase1 2>/dev/null | head -1 || true)
fi

BEST_MODEL="${LATEST_RUN}/weights/best.pt"
if [ ! -f "$BEST_MODEL" ]; then
    BEST_MODEL="${LATEST_RUN}/weights/last.pt"
fi

if [ ! -f "$BEST_MODEL" ]; then
    echo "ERROR: No trained model found in ${LATEST_RUN}"
    exit 1
fi

echo ""
echo "  Trained model: ${BEST_MODEL}"
MODEL_SIZE=$(du -h "$BEST_MODEL" | cut -f1)
echo "  Model size: ${MODEL_SIZE}"
echo ""

# =============================================================================
# STEP 3: Deploy to production
# =============================================================================
if [ "$SKIP_DEPLOY" = true ]; then
    echo "  Skipping deployment (--skip-deploy)"
    echo ""
    echo "  To deploy manually:"
    echo "    cp ${BEST_MODEL} ${PRODUCTION_MODEL}"
    echo "    cd ${PROJECT_ROOT} && docker compose build ml-detector && docker compose up -d ml-detector"
    echo ""
else
    echo "============================================================================="
    echo "  STEP 3: Deploying to production"
    echo "============================================================================="
    echo ""
    
    # Backup current model
    if [ -f "$PRODUCTION_MODEL" ]; then
        BACKUP="${PRODUCTION_MODEL}.bak_$(date +%Y%m%d_%H%M%S)"
        cp "$PRODUCTION_MODEL" "$BACKUP"
        echo "  Backed up current model to: ${BACKUP}"
    fi
    
    # Copy new model
    mkdir -p "$(dirname "$PRODUCTION_MODEL")"
    cp "$BEST_MODEL" "$PRODUCTION_MODEL"
    echo "  Deployed model to: ${PRODUCTION_MODEL}"
    
    # Rebuild and restart ml-detector container
    echo ""
    echo "  Rebuilding ml-detector container..."
    cd "${PROJECT_ROOT}"
    docker compose build ml-detector
    
    echo ""
    echo "  Restarting ml-detector container..."
    docker compose up -d ml-detector
    
    # Wait for health check
    echo ""
    echo "  Waiting for ml-detector to be healthy..."
    for i in $(seq 1 30); do
        if docker compose exec -T ml-detector curl -sf http://localhost:8001/health > /dev/null 2>&1; then
            echo "  ✅ ml-detector is healthy!"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo "  WARNING: ml-detector health check timed out. Check logs."
        fi
        sleep 2
    done
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "============================================================================="
echo "  PIPELINE COMPLETE"
echo "============================================================================="
echo "  Finished:   $(date)"
echo "  Dataset:    ${DATASET_DIR}"
echo "  Model:      ${BEST_MODEL}"
if [ "$SKIP_DEPLOY" = false ]; then
    echo "  Deployed:   ${PRODUCTION_MODEL}"
fi
echo "  Log:        ${LOG_FILE}"
echo ""

# Print the training summary JSON if available
SUMMARY=$(ls -t "${RUNS_DIR}"/deer_v2_*_summary.json 2>/dev/null | head -1 || true)
if [ -n "$SUMMARY" ] && [ -f "$SUMMARY" ]; then
    echo "  Training Summary:"
    python3 -c "
import json
with open('${SUMMARY}') as f:
    s = json.load(f)
m = s.get('test_metrics', {})
print(f\"    Architecture: {s.get('architecture', 'N/A')}\")
print(f\"    Epochs:       {s.get('epochs_total', 'N/A')}\")
print(f\"    mAP50:        {m.get('map50', 'N/A')}\")
print(f\"    mAP50-95:     {m.get('map50_95', 'N/A')}\")
print(f\"    Precision:    {m.get('precision', 'N/A')}\")
print(f\"    Recall:       {m.get('recall', 'N/A')}\")
print(f\"    Model size:   {s.get('model_size_mb', 'N/A')} MB\")
"
fi

echo "============================================================================="
