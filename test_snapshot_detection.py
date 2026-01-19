"""
Test model performance on Ring snapshot images vs video frames.

This script:
1. Loads saved Ring snapshots from data/ring_snapshots/
2. Runs ML detection on each snapshot
3. Compares to detection results from video frames (if available)
4. Generates performance report

Run this after 24-48 hours of snapshot collection.
"""
import sys
from pathlib import Path
import sqlite3
import cv2
import numpy as np
from typing import List, Dict, Tuple
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def load_model():
    """Load the YOLOv8 model."""
    from ultralytics import YOLO
    
    model_paths = [
        "models/production/best.pt",
        "models/deer_detector_best.pt",
        "yolov8n.pt"
    ]
    
    for path in model_paths:
        if Path(path).exists():
            print(f"✓ Loading model from {path}")
            return YOLO(path)
    
    raise FileNotFoundError("No model file found")

def get_snapshots_from_db() -> List[Dict]:
    """Get all Ring events with saved snapshots."""
    conn = sqlite3.connect('data/training.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("""
        SELECT id, camera_id, event_type, timestamp, 
               snapshot_path, deer_detected, detection_confidence
        FROM ring_events 
        WHERE snapshot_path IS NOT NULL
        ORDER BY timestamp DESC
    """)
    
    snapshots = [dict(row) for row in c.fetchall()]
    conn.close()
    
    return snapshots

def run_detection_on_snapshot(model, snapshot_path: str, confidence_threshold: float = 0.15) -> Tuple[bool, float, int]:
    """
    Run detection on a snapshot image.
    
    Returns:
        (detected, max_confidence, detection_count)
    """
    if not Path(snapshot_path).exists():
        print(f"  ⚠️  Snapshot not found: {snapshot_path}")
        return False, 0.0, 0
    
    # Load image
    img = cv2.imread(snapshot_path)
    if img is None:
        print(f"  ⚠️  Failed to load image: {snapshot_path}")
        return False, 0.0, 0
    
    # Run detection
    results = model.predict(img, conf=confidence_threshold, verbose=False)
    
    # Parse results
    detections = []
    if len(results) > 0 and results[0].boxes is not None:
        boxes = results[0].boxes
        for i in range(len(boxes)):
            conf = float(boxes.conf[i])
            detections.append(conf)
    
    if detections:
        max_conf = max(detections)
        return True, max_conf, len(detections)
    else:
        return False, 0.0, 0

def analyze_snapshot_performance(model, snapshots: List[Dict], threshold: float = 0.15):
    """Analyze model performance on all snapshots."""
    
    print("\n" + "=" * 80)
    print(f"TESTING MODEL ON {len(snapshots)} SNAPSHOTS")
    print("=" * 80)
    print(f"Detection threshold: {threshold}\n")
    
    results = []
    
    for idx, snapshot in enumerate(snapshots, 1):
        print(f"[{idx}/{len(snapshots)}] {snapshot['snapshot_path']}")
        print(f"  Timestamp: {snapshot['timestamp']}")
        print(f"  Camera: {snapshot['camera_id']}")
        
        detected, confidence, count = run_detection_on_snapshot(
            model, 
            snapshot['snapshot_path'],
            confidence_threshold=threshold
        )
        
        # Get stored result (from original instant detection)
        original_detected = snapshot['deer_detected']
        original_confidence = snapshot['detection_confidence']
        
        print(f"  Original Detection: {original_detected} (conf={original_confidence:.3f})" if original_confidence else f"  Original Detection: {original_detected}")
        print(f"  Re-run Detection: {detected} (conf={confidence:.3f}, count={count})")
        
        # Check for discrepancies
        if original_detected != detected:
            print(f"  ⚠️  MISMATCH: Original={original_detected}, Re-run={detected}")
        
        results.append({
            "event_id": snapshot['id'],
            "snapshot_path": snapshot['snapshot_path'],
            "timestamp": snapshot['timestamp'],
            "camera_id": snapshot['camera_id'],
            "original_detected": original_detected,
            "original_confidence": original_confidence,
            "rerun_detected": detected,
            "rerun_confidence": confidence,
            "detection_count": count,
            "mismatch": original_detected != detected
        })
        
        print()
    
    return results

def generate_report(results: List[Dict], threshold: float):
    """Generate performance analysis report."""
    
    print("=" * 80)
    print("SNAPSHOT DETECTION PERFORMANCE REPORT")
    print("=" * 80)
    print(f"\nThreshold: {threshold}")
    print(f"Total Snapshots: {len(results)}")
    
    # Calculate statistics
    original_detections = sum(1 for r in results if r['original_detected'])
    rerun_detections = sum(1 for r in results if r['rerun_detected'])
    mismatches = sum(1 for r in results if r['mismatch'])
    
    avg_confidence_detected = np.mean([r['rerun_confidence'] for r in results if r['rerun_detected']]) if rerun_detections > 0 else 0
    avg_confidence_all = np.mean([r['rerun_confidence'] for r in results])
    
    print(f"\nDetection Summary:")
    print(f"  Original Detections: {original_detections} ({original_detections/len(results)*100:.1f}%)")
    print(f"  Re-run Detections: {rerun_detections} ({rerun_detections/len(results)*100:.1f}%)")
    print(f"  Mismatches: {mismatches} ({mismatches/len(results)*100:.1f}%)")
    
    print(f"\nConfidence Statistics:")
    print(f"  Average (all snapshots): {avg_confidence_all:.3f}")
    print(f"  Average (detected only): {avg_confidence_detected:.3f}")
    print(f"  Max: {max([r['rerun_confidence'] for r in results]):.3f}")
    print(f"  Min: {min([r['rerun_confidence'] for r in results]):.3f}")
    
    # Breakdown by camera
    cameras = set(r['camera_id'] for r in results)
    print(f"\nBy Camera:")
    for camera in sorted(cameras):
        camera_results = [r for r in results if r['camera_id'] == camera]
        camera_detections = sum(1 for r in camera_results if r['rerun_detected'])
        print(f"  {camera}: {camera_detections}/{len(camera_results)} detections ({camera_detections/len(camera_results)*100:.1f}%)")
    
    # Show mismatches
    if mismatches > 0:
        print(f"\n⚠️  Mismatch Details:")
        for r in results:
            if r['mismatch']:
                print(f"  Event #{r['event_id']} ({r['timestamp']})")
                print(f"    Original: {r['original_detected']} (conf={r['original_confidence']:.3f})" if r['original_confidence'] else f"    Original: {r['original_detected']}")
                print(f"    Re-run: {r['rerun_detected']} (conf={r['rerun_confidence']:.3f})")
    
    # Recommendations
    print(f"\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    if len(results) < 20:
        print("⚠️  Sample size too small (< 20 snapshots)")
        print("   Collect more data before making conclusions")
        print(f"   Current: {len(results)}, Recommended: 50+")
    
    if avg_confidence_detected < 0.30:
        print("\n⚠️  Low average confidence on snapshots")
        print(f"   Average: {avg_confidence_detected:.3f}")
        print("   Consider:")
        print("   1. Lower detection threshold (currently {threshold})")
        print("   2. Retrain model with snapshot images included")
        print("   3. Use burst approach (3 snapshots) to increase chances")
    
    if mismatches > len(results) * 0.2:
        print("\n⚠️  High mismatch rate (> 20%)")
        print("   This could indicate:")
        print("   1. Model non-deterministic (unlikely)")
        print("   2. Image loading/preprocessing differences")
        print("   3. Need for consistent threshold across runs")
    
    if rerun_detections > 0:
        print("\n✓ Model DOES work on Ring snapshots")
        print(f"  Detection rate: {rerun_detections/len(results)*100:.1f}%")
        print(f"  Average confidence: {avg_confidence_detected:.3f}")
        print("\n  Recommendation: Proceed with burst snapshot approach")
        print("  - Use 3 snapshots per event")
        print(f"  - Threshold: {max(0.20, avg_confidence_detected - 0.05):.2f} (slightly below average)")
        print("  - Video confirmation for comprehensive analysis")
    else:
        print("\n❌ Model did NOT detect deer in any snapshots")
        print("  This could mean:")
        print("  1. No deer actually present in these events")
        print("  2. Snapshot quality insufficient for model")
        print("  3. Model trained only on video frames, needs snapshot training")
        print("\n  Recommendation: Collect labeled snapshot dataset and retrain")
    
    # Save results to JSON
    output_file = "data/snapshot_test_results.json"
    Path(output_file).parent.mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump({
            "threshold": threshold,
            "total_snapshots": len(results),
            "summary": {
                "original_detections": original_detections,
                "rerun_detections": rerun_detections,
                "mismatches": mismatches,
                "avg_confidence_all": float(avg_confidence_all),
                "avg_confidence_detected": float(avg_confidence_detected)
            },
            "results": results
        }, f, indent=2)
    
    print(f"\n✓ Detailed results saved to: {output_file}")

def test_specific_snapshot(model, snapshot_path: str):
    """Test a specific snapshot and show detailed results."""
    print(f"Testing snapshot: {snapshot_path}\n")
    
    if not Path(snapshot_path).exists():
        print(f"❌ File not found: {snapshot_path}")
        return
    
    # Load and display image info
    img = cv2.imread(snapshot_path)
    print(f"Image size: {img.shape[1]}x{img.shape[0]}")
    print(f"File size: {Path(snapshot_path).stat().st_size:,} bytes")
    
    # Test at multiple thresholds
    print(f"\nTesting at multiple thresholds:")
    for threshold in [0.10, 0.15, 0.20, 0.25, 0.30]:
        detected, confidence, count = run_detection_on_snapshot(model, snapshot_path, threshold)
        print(f"  Threshold {threshold:.2f}: detected={detected}, confidence={confidence:.3f}, count={count}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test model on Ring snapshots")
    parser.add_argument("--threshold", type=float, default=0.15, help="Detection confidence threshold")
    parser.add_argument("--test-file", type=str, help="Test a specific snapshot file")
    args = parser.parse_args()
    
    print("=" * 80)
    print("RING SNAPSHOT MODEL TESTING")
    print("=" * 80)
    
    # Load model
    try:
        model = load_model()
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        sys.exit(1)
    
    # Test specific file if provided
    if args.test_file:
        test_specific_snapshot(model, args.test_file)
        sys.exit(0)
    
    # Get saved snapshots
    snapshots = get_snapshots_from_db()
    
    if not snapshots:
        print("\n⚠️  No snapshots found in database")
        print("\nPossible reasons:")
        print("1. Coordinator hasn't captured any motion events yet")
        print("2. Migration script hasn't been run (snapshot_path column missing)")
        print("3. Snapshots being captured but not saved to disk")
        print("\nWait 24-48 hours after deploying snapshot-saving coordinator,")
        print("then run this script again.")
        sys.exit(0)
    
    print(f"\n✓ Found {len(snapshots)} saved snapshots")
    
    # Verify files exist
    existing_snapshots = [s for s in snapshots if Path(s['snapshot_path']).exists()]
    missing = len(snapshots) - len(existing_snapshots)
    
    if missing > 0:
        print(f"⚠️  {missing} snapshot files are missing from disk")
    
    if not existing_snapshots:
        print("❌ No snapshot files found on disk")
        sys.exit(1)
    
    # Run analysis
    results = analyze_snapshot_performance(model, existing_snapshots, threshold=args.threshold)
    
    # Generate report
    generate_report(results, threshold=args.threshold)
