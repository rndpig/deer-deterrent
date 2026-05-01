SELECT substr(timestamp,12,8) as t, camera_id, event_type, deer_detected FROM ring_events WHERE timestamp >= '2026-04-24 01:00:00' AND timestamp < '2026-04-24 02:00:00' ORDER BY timestamp;
