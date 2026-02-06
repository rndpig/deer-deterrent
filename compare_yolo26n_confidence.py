"""
Compare detection confidence between old baseline YOLOv8n and new YOLO26n models.
Run this on the 7 highest-confidence deer snapshots.
"""
import requests
import json
from pathlib import Path

API_BASE = "https://deer-api.rndpig.com"

# Top 7 deer snapshots by confidence
SNAPSHOT_IDS = [19697, 19699, 17359, 5766, 17363, 17365, 17361]

def main():
    print("=" * 80)
    print("YOLO26n vs YOLOv8n Baseline - Confidence Comparison")
    print("=" * 80)
    print(f"\nRe-detecting {len(SNAPSHOT_IDS)} snapshots with YOLO26n (OpenVINO FP16)...")
    print()
    
    results = []
    
    for snapshot_id in SNAPSHOT_IDS:
        # Get current snapshot data
        response = requests.get(f"{API_BASE}/api/snapshots?limit=1")
        response.raise_for_status()
        events = response.json()['snapshots']
        
        # Find our snapshot
        event = None
        response_all = requests.get(f"{API_BASE}/api/snapshots?limit=500&with_deer=true")
        for e in response_all.json()['snapshots']:
            if e['id'] == snapshot_id:
                event = e
                break
        
        if not event:
            print(f"Snapshot #{snapshot_id}: NOT FOUND, skipping")
            continue
        
        old_confidence = event.get('detection_confidence', 0.0)
        
        # Re-run detection with new model (which should be OpenVINO YOLO26n)
        print(f"Snapshot #{snapshot_id}: ", end="", flush=True)
        
        rerun_response = requests.post(
            f"{API_BASE}/api/snapshots/{snapshot_id}/rerun-detection",
            params={"threshold": 0.60}
        )
        rerun_response.raise_for_status()
        
        rerun_result = rerun_response.json()
        new_confidence = rerun_result.get('max_confidence', 0.0)
        
        # Calculate change
        change = new_confidence - old_confidence
        change_pct = (change / old_confidence * 100) if old_confidence > 0 else 0
        
        results.append({
            'id': snapshot_id,
            'old_conf': old_confidence,
            'new_conf': new_confidence,
            'change': change,
            'change_pct': change_pct,
            'timestamp': event.get('timestamp')
        })
        
        symbol = "🔺" if change > 0 else "🔻" if change < 0 else "="
        print(f"Old: {old_confidence:.3f} → New: {new_confidence:.3f} {symbol} ({change:+.3f}, {change_pct:+.1f}%)")
    
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()
    
    # Calculate statistics
    avg_old = sum(r['old_conf'] for r in results) / len(results)
    avg_new = sum(r['new_conf'] for r in results) / len(results)
    avg_change = sum(r['change'] for r in results) / len(results)
    avg_change_pct = sum(r['change_pct'] for r in results) / len(results)
    
    improved = sum(1 for r in results if r['change'] > 0)
    declined = sum(1 for r in results if r['change'] < 0)
    unchanged = sum(1 for r in results if r['change'] == 0)
    
    print(f"Average Confidence:")
    print(f"  YOLOv8n Baseline:  {avg_old:.3f}")
    print(f"  YOLO26n v1.1:      {avg_new:.3f}")
    print(f"  Change:            {avg_change:+.3f} ({avg_change_pct:+.1f}%)")
    print()
    print(f"Detection Changes:")
    print(f"  Improved:  {improved}/7 snapshots")
    print(f"  Declined:  {declined}/7 snapshots")
    print(f"  Unchanged: {unchanged}/7 snapshots")
    print()
    
    # Determine winner
    if avg_new > avg_old:
        print(f"🏆 YOLO26n v1.1 is {avg_change_pct:.1f}% more confident on average!")
    elif avg_new < avg_old:
        print(f"⚠️  YOLOv8n baseline was {-avg_change_pct:.1f}% more confident")
    else:
        print("📊 Both models have identical average confidence")
    
    print()
    print("=" * 80)
    print()
    
    # Save results
    output_path = Path("data/model_registry/yolo26n_baseline_comparison.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump({
            'snapshots': results,
            'summary': {
                'avg_old': avg_old,
                'avg_new': avg_new,
                'avg_change': avg_change,
                'avg_change_pct': avg_change_pct,
                'improved': improved,
                'declined': declined,
                'unchanged': unchanged
            }
        }, f, indent=2)
    
    print(f"Results saved to: {output_path}")
    print()

if __name__ == "__main__":
    main()
