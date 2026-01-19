"""
Quick verification that snapshot saving is working.
Run this after deploying the modified coordinator.
"""
from pathlib import Path
import time
import sqlite3

def check_snapshot_system():
    """Verify snapshot collection system is working."""
    
    print("=" * 80)
    print("SNAPSHOT COLLECTION VERIFICATION")
    print("=" * 80)
    
    # Check 1: Directory exists
    snapshot_dir = Path("data/ring_snapshots")
    if snapshot_dir.exists():
        print("✓ Snapshot directory exists: data/ring_snapshots/")
        
        # Count files
        snapshots = list(snapshot_dir.glob("*.jpg"))
        print(f"  Files saved: {len(snapshots)}")
        
        if snapshots:
            # Show latest
            latest = max(snapshots, key=lambda p: p.stat().st_mtime)
            size = latest.stat().st_size
            mtime = latest.stat().st_mtime
            age = time.time() - mtime
            
            print(f"\n  Latest snapshot:")
            print(f"    File: {latest.name}")
            print(f"    Size: {size:,} bytes")
            print(f"    Age: {age/60:.1f} minutes ago")
            
            if age > 3600:
                print("    ⚠️  No recent snapshots (> 1 hour old)")
                print("       Check if coordinator is running")
                print("       Check if motion events are occurring")
        else:
            print("  ⚠️  No snapshots saved yet")
            print("     Wait for a motion event to occur")
    else:
        print("⚠️  Snapshot directory doesn't exist yet")
        print("   Will be created on first motion event")
    
    # Check 2: Database schema
    print("\n" + "-" * 80)
    print("Database Schema Check")
    print("-" * 80)
    
    db_path = Path("data/training.db")
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        c = conn.cursor()
        
        # Check table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ring_events'")
        if c.fetchone():
            # Check column exists
            c.execute("PRAGMA table_info(ring_events)")
            columns = [row[1] for row in c.fetchall()]
            
            if 'snapshot_path' in columns:
                print("✓ snapshot_path column exists")
                
                # Check for recent entries
                c.execute("""
                    SELECT COUNT(*) FROM ring_events 
                    WHERE snapshot_path IS NOT NULL
                """)
                count = c.fetchone()[0]
                print(f"  Events with snapshots: {count}")
                
                if count > 0:
                    c.execute("""
                        SELECT snapshot_path, timestamp 
                        FROM ring_events 
                        WHERE snapshot_path IS NOT NULL 
                        ORDER BY id DESC 
                        LIMIT 1
                    """)
                    row = c.fetchone()
                    print(f"  Latest: {row[1]} -> {row[0]}")
            else:
                print("❌ snapshot_path column missing")
                print("   Run: python migrate_snapshot_path.py")
        else:
            print("⚠️  ring_events table doesn't exist yet")
            print("   Will be created when coordinator logs first event")
        
        conn.close()
    else:
        print("⚠️  Database doesn't exist yet")
        print("   Will be created when backend starts")
    
    # Check 3: Coordinator status
    print("\n" + "-" * 80)
    print("System Status")
    print("-" * 80)
    
    # Check if coordinator is logging
    print("\nTo verify coordinator is running with new code:")
    print("  1. Trigger a motion event (wave in front of camera)")
    print("  2. Check logs for: '✓ Saved snapshot to data/ring_snapshots/...'")
    print("  3. Verify file appears in data/ring_snapshots/")
    print("  4. Verify database updated with snapshot_path")
    
    print("\nExpected behavior on motion event:")
    print("  [Coordinator] ⚡ INSTANT motion detected on camera front_yard")
    print("  [Coordinator] ✓ Saved snapshot to data/ring_snapshots/event_20260118_143022_front_yard_snapshot.jpg")
    print("  [Coordinator] Logged Ring event #123")
    print("  [Coordinator] ✓ Using instant snapshot for real-time detection")
    
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    
    if snapshot_dir.exists() and list(snapshot_dir.glob("*.jpg")):
        print("\n✓ System is collecting snapshots!")
        print(f"  Collected: {len(list(snapshot_dir.glob('*.jpg')))} snapshots")
        print("\nWait 24-48 hours to collect 20-50 snapshots, then run:")
        print("  python test_snapshot_detection.py")
    else:
        print("\n⏳ Waiting for first motion event...")
        print("\nTroubleshooting:")
        print("  1. Verify coordinator is running")
        print("  2. Trigger a test motion event")
        print("  3. Check coordinator logs for errors")
        print("  4. Verify MQTT connection is working")
        print("\nRun this script again after motion event occurs.")

if __name__ == "__main__":
    check_snapshot_system()
