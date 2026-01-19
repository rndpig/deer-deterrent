"""
Check Ring events for January 16, 2026 at 10:06 PM Central time.
"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# Database path  
DB_PATH = Path("data/training.db")

def check_ring_events():
    """Check Ring events around Jan 16, 2026 10:06 PM Central."""
    
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        return
    
    print(f"✓ Database found at {DB_PATH}")
    print(f"Database size: {DB_PATH.stat().st_size / 1024 / 1024:.2f} MB")
    print()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if ring_events table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ring_events'")
    if not cursor.fetchone():
        print("⚠ ring_events table does not exist in database")
        conn.close()
        return
    
    print("✓ ring_events table exists")
    print()
    
    # Get total count of ring events
    cursor.execute("SELECT COUNT(*) as count FROM ring_events")
    total_events = cursor.fetchone()['count']
    print(f"Total Ring events in database: {total_events}")
    print()
    
    # Jan 16, 2026 10:06 PM Central = Jan 17, 2026 04:06 UTC (assuming CST -6)
    # But let's search a wider window to be safe
    target_date_start = "2026-01-16 20:00:00"  # 8 PM local
    target_date_end = "2026-01-17 02:00:00"    # 2 AM local next day
    
    print(f"Searching for events between {target_date_start} and {target_date_end} (local time)")
    print()
    
    cursor.execute("""
        SELECT * FROM ring_events 
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY timestamp DESC
    """, (target_date_start, target_date_end))
    
    events = cursor.fetchall()
    
    if not events:
        print("❌ No Ring events found in the target time window")
        print()
        print("Checking recent events (last 7 days):")
        cursor.execute("""
            SELECT * FROM ring_events 
            WHERE datetime(timestamp) >= datetime('now', '-7 days')
            ORDER BY timestamp DESC
            LIMIT 20
        """)
        recent_events = cursor.fetchall()
        
        if recent_events:
            print(f"\nFound {len(recent_events)} recent events:")
            for event in recent_events:
                print(f"\n  Event ID: {event['id']}")
                print(f"  Camera: {event['camera_id']}")
                print(f"  Type: {event['event_type']}")
                print(f"  Timestamp: {event['timestamp']}")
                print(f"  Snapshot available: {event['snapshot_available']}")
                print(f"  Snapshot size: {event['snapshot_size']} bytes" if event['snapshot_size'] else "  Snapshot size: None")
                print(f"  Processed: {event['processed']}")
                if event['processed']:
                    print(f"  Deer detected: {event['deer_detected']}")
                    print(f"  Confidence: {event['detection_confidence']}")
        else:
            print("  No recent events found in database")
    else:
        print(f"✓ Found {len(events)} events in the target time window:")
        
        for event in events:
            print(f"\n{'='*60}")
            print(f"Event ID: {event['id']}")
            print(f"Camera ID: {event['camera_id']}")
            print(f"Event Type: {event['event_type']}")
            print(f"Timestamp: {event['timestamp']}")
            print(f"Snapshot Available: {event['snapshot_available']}")
            print(f"Snapshot Size: {event['snapshot_size']} bytes" if event['snapshot_size'] else "Snapshot Size: None")
            print(f"Recording URL: {event['recording_url'][:80] if event['recording_url'] else 'None'}...")
            print(f"Processed: {event['processed']}")
            
            if event['processed']:
                print(f"Deer Detected: {event['deer_detected']}")
                print(f"Detection Confidence: {event['detection_confidence']}")
                if event['error_message']:
                    print(f"Error: {event['error_message']}")
            else:
                print("⚠ Event was NOT processed for detection")
            
            print(f"Created: {event['created_at']}")
    
    conn.close()
    
    print()
    print("="*60)
    print("Checking coordinator logs for more information...")
    print("="*60)
    
    # Try to get coordinator logs
    import docker
    try:
        client = docker.from_env()
        container = client.containers.get("deer-coordinator")
        
        print("\nCoordinator container status:", container.status)
        
        # Get logs from Jan 16-17
        print("\nCoordinator logs (last 500 lines):")
        logs = container.logs(tail=500, timestamps=True).decode('utf-8', errors='replace')
        
        # Filter for Jan 16-17 entries
        jan16_logs = []
        for line in logs.split('\n'):
            if '2026-01-16' in line or '2026-01-17' in line:
                jan16_logs.append(line)
        
        if jan16_logs:
            print(f"\nFound {len(jan16_logs)} log entries from Jan 16-17:")
            for log_line in jan16_logs:
                print(log_line)
        else:
            print("\n⚠ No log entries found from Jan 16-17")
            print("\nShowing last 50 lines of coordinator logs:")
            for line in logs.split('\n')[-50:]:
                print(line)
    
    except Exception as e:
        print(f"\n⚠ Could not access coordinator logs: {e}")
        print("  (Container may not be running)")


if __name__ == "__main__":
    print("="*60)
    print("Deer Deterrent - Jan 16, 2026 Event Investigation")
    print("="*60)
    print()
    check_ring_events()
