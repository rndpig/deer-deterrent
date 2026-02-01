#!/bin/bash
# Quick status check for Phase 1 progress

echo "=============================================="
echo "DEER DETERRENT - Phase 1 Status Check"
echo "=============================================="
echo ""

# Check dataset
if [ -d "data/training_datasets/v1.0_2026-01-baseline" ]; then
    echo "✅ Dataset v1.0: READY"
    echo "   Location: data/training_datasets/v1.0_2026-01-baseline/"
    train_count=$(ls data/training_datasets/v1.0_2026-01-baseline/images/train/*.jpg 2>/dev/null | wc -l)
    val_count=$(ls data/training_datasets/v1.0_2026-01-baseline/images/val/*.jpg 2>/dev/null | wc -l)
    test_count=$(ls data/training_datasets/v1.0_2026-01-baseline/images/test/*.jpg 2>/dev/null | wc -l)
    echo "   Train: $train_count | Val: $val_count | Test: $test_count"
else
    echo "❌ Dataset v1.0: NOT FOUND"
fi

echo ""

# Check model registry
if [ -f "models/registry.json" ]; then
    echo "✅ Model Registry: CREATED"
    echo "   Location: models/registry.json"
else
    echo "❌ Model Registry: NOT FOUND"
fi

echo ""

# Check baseline benchmark
if [ -f "models/yolov8n_baseline_validation_results.json" ]; then
    echo "✅ Baseline Benchmark: COMPLETE"
    echo "   Results: models/yolov8n_baseline_validation_results.json"
    
    # Extract metrics if jq is available
    if command -v jq &> /dev/null; then
        mAP50=$(jq -r '.metrics.mAP50' models/yolov8n_baseline_validation_results.json 2>/dev/null)
        if [ "$mAP50" != "null" ]; then
            echo "   mAP50: $mAP50"
        fi
    else
        cat models/yolov8n_baseline_validation_results.json
    fi
else
    echo "⏳ Baseline Benchmark: IN PROGRESS or PENDING"
    echo "   Check: python3 scripts/benchmark_yolov8_baseline.py"
    
    # Check if process is running
    if pgrep -f "benchmark_yolov8_baseline.py" > /dev/null; then
        echo "   Status: RUNNING"
    else
        echo "   Status: NOT STARTED"
    fi
fi

echo ""
echo "=============================================="
echo "Next Steps:"
echo "=============================================="
echo "1. Wait for benchmark to complete (if running)"
echo "2. Review baseline metrics"
echo "3. Train YOLO26:"
echo "   python3 -c \"from ultralytics import YOLO; \\"
echo "   model = YOLO('yolo26n.pt'); \\"
echo "   model.train(data='data/training_datasets/v1.0_2026-01-baseline/data.yaml', epochs=100, device='cpu')\""
echo ""
echo "For full documentation, see: PHASE1_PROGRESS.md"
echo "=============================================="
