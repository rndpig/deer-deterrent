#!/usr/bin/env python3
"""
Coordinator Service - Ring Camera → ML Detection → Irrigation Activation
Handles the complete flow from camera event to deterrent action
"""

import os
import logging
import json
import base64
import hashlib
import itertools
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import asyncio
import queue
import threading

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
import httpx
import requests
import paho.mqtt.client as mqtt

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/coordinator.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Deer Deterrent Coordinator",
    description="Coordinates Ring cameras, ML detection, and irrigation activation",
    version="1.0.0"
)

# Configuration
CONFIG = {
    "ML_DETECTOR_URL": os.getenv("ML_DETECTOR_URL", "http://ml-detector:8001"),
    "BACKEND_API_URL": os.getenv("BACKEND_API_URL", "http://backend:8000"),
    "MQTT_HOST": os.getenv("MQTT_HOST", "mosquitto"),
    "MQTT_PORT": int(os.getenv("MQTT_PORT", "1883")),
    "MQTT_USER": os.getenv("MQTT_USER", ""),
    "MQTT_PASSWORD": os.getenv("MQTT_PASSWORD", ""),
    "RAINBIRD_IP": os.getenv("RAINBIRD_IP", ""),
    "RAINBIRD_PASSWORD": os.getenv("RAINBIRD_PASSWORD", ""),
    "RAINBIRD_ZONE": os.getenv("RAINBIRD_ZONE", "1"),
    "RAINBIRD_DURATION_SECONDS": int(os.getenv("RAINBIRD_DURATION_SECONDS", "30")),
    "CONFIDENCE_THRESHOLD": float(os.getenv("CONFIDENCE_THRESHOLD", "0.30")),
    "COOLDOWN_SECONDS": int(os.getenv("COOLDOWN_SECONDS", "300")),
    "ENABLE_IRRIGATION": os.getenv("ENABLE_IRRIGATION", "true").lower() == "true",
    "ACTIVE_HOURS_ENABLED": True,  # Will be synced from backend settings
    "ACTIVE_HOURS_START": int(os.getenv("ACTIVE_HOURS_START", "20")),
    "ACTIVE_HOURS_END": int(os.getenv("ACTIVE_HOURS_END", "6")),
    "ENABLED_CAMERAS": [c.strip() for c in os.getenv("ENABLED_CAMERAS", "").split(",") if c.strip()],  # Synced from backend settings
    # Periodic snapshot polling (interval derived from snapshot_frequency setting)
    "ENABLE_PERIODIC_SNAPSHOTS": os.getenv("ENABLE_PERIODIC_SNAPSHOTS", "false").lower() == "true",
    "SNAPSHOT_FREQUENCY": 60,  # Ring capture frequency in seconds, synced from backend settings
    "RING_LOCATION_ID": os.getenv("RING_LOCATION_ID", ""),  # Needed for MQTT topics
    "CAMERA_ZONES": {},  # Camera ID → Rainbird zone number, synced from backend settings
    "SNAPSHOT_RETENTION_DAYS": int(os.getenv("SNAPSHOT_RETENTION_DAYS", "3")),  # Days to keep no-deer periodic snapshots; synced from backend
    "INTERNAL_API_KEY": os.getenv("INTERNAL_API_KEY", ""),  # API key for service-to-service auth
}

# Per-camera chase sequences are configured via the backend's `camera_zones`
# setting (Camera ID → ordered list of zones). The coordinator fires those zones
# back-to-back to chase deer in the appropriate direction. Legacy values that
# are bare ints are normalized to single-element lists at config-load time.


def _coerce_zone_list(value) -> list[int]:
    """Normalize a configured zone value (int | list | None) to list[int]."""
    if value is None or value == "":
        return []
    if isinstance(value, list):
        out = []
        for z in value:
            try:
                out.append(int(z))
            except (TypeError, ValueError):
                continue
        return out
    try:
        return [int(value)]
    except (TypeError, ValueError):
        return []


def build_chase_chain(camera_id: str | None, fallback_zone: int | None = None) -> list[int]:
    """Return the ordered zone list to fire for a given camera.

    Reads CONFIG['CAMERA_ZONES'][camera_id] which may be a list (chase sequence)
    or a bare int (single-zone trigger). Falls back to [fallback_zone] if the
    camera has no mapping.
    """
    cam_map = CONFIG.get("CAMERA_ZONES", {}) or {}
    chain = _coerce_zone_list(cam_map.get(camera_id))
    if chain:
        return chain
    if fallback_zone is not None:
        return [int(fallback_zone)]
    return []


async def run_chase(zones: list[int], duration: int) -> bool:
    """Fire each zone sequentially, awaiting `duration` seconds between activations.

    Returns True if at least the first zone activated successfully.
    """
    if not zones:
        return False
    first_ok = await activate_rainbird(str(zones[0]), duration)
    if len(zones) == 1:
        return first_ok
    logger.info(f"🦌 Chase chain queued: {zones} ({duration}s each)")
    for next_zone in zones[1:]:
        await asyncio.sleep(duration)
        await activate_rainbird(str(next_zone), duration)
    return first_ok


def get_api_headers() -> Dict[str, str]:
    """Get headers for backend API calls (includes API key if configured)."""
    headers = {"Content-Type": "application/json"}
    if CONFIG["INTERNAL_API_KEY"]:
        headers["X-API-Key"] = CONFIG["INTERNAL_API_KEY"]
    return headers


# State tracking
last_activation_time: Optional[datetime] = None
mqtt_client: Optional[mqtt.Client] = None
event_queue: queue.PriorityQueue = queue.PriorityQueue()  # Priority queue: motion > periodic
event_counter = itertools.count()  # Monotonic counter for PriorityQueue tiebreaking
camera_snapshots: Dict[str, bytes] = {}  # Store latest snapshot for each camera
last_periodic_snapshot_time: Dict[str, datetime] = {}  # Track last periodic snapshot per camera
last_snapshot_hash: Dict[str, str] = {}  # Track snapshot hashes to prevent duplicate processing
last_motion_ring_event: Dict[str, int] = {}  # Track most recent ring_event_id per camera (for linking recordings)
chase_in_progress: Dict[str, bool] = {}  # Per-camera flag: True while a chase RTSP recording is being captured

# Video queue: accumulate recording URLs during active hours, process after
PENDING_VIDEOS_FILE = Path("/app/data/pending_videos.json")
RECORDINGS_DIR = Path("/app/snapshots/recordings")


def load_pending_videos() -> list:
    """Load pending video queue from disk (crash-resilient)."""
    try:
        if PENDING_VIDEOS_FILE.exists():
            data = json.loads(PENDING_VIDEOS_FILE.read_text())
            if isinstance(data, list):
                return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load pending videos file: {e}")
    return []


def save_pending_videos(queue_list: list):
    """Persist pending video queue to disk."""
    try:
        PENDING_VIDEOS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PENDING_VIDEOS_FILE.write_text(json.dumps(queue_list, indent=2))
    except OSError as e:
        logger.error(f"Failed to save pending videos file: {e}")


def extract_recording_time_from_url(url: str) -> Optional[str]:
    """Extract the actual recording start time from a Ring download URL's JWT token.
    
    Ring download URLs contain a security_token JWT with a 'start' field
    (epoch milliseconds) indicating when the video was actually recorded.
    This is more accurate than datetime.now() since Ring may deliver
    recording URLs hours after the video was captured.
    """
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        token = qs.get("security_token", [None])[0]
        if not token:
            return None
        # Decode JWT payload (second segment) without verification
        payload_b64 = token.split(".")[1]
        # Add padding
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        start_ms = payload.get("start")
        if start_ms:
            recording_time = datetime.fromtimestamp(start_ms / 1000)
            logger.debug(f"Extracted recording time from URL JWT: {recording_time.isoformat()}")
            return recording_time.isoformat()
    except Exception as e:
        logger.debug(f"Could not extract recording time from URL: {e}")
    return None


def queue_video_for_processing(camera_id: str, recording_url: str, motion_time: str = None, ring_event_id: int = None):
    """Download video immediately and add to pending queue for batch processing.
    
    Downloads the MP4 before the Ring URL expires (~15 min TTL), then stores
    the local file path in pending_videos.json for deferred frame extraction.
    """
    pending = load_pending_videos()
    # Deduplicate by URL within current pending queue
    if any(v.get("url") == recording_url for v in pending):
        logger.debug(f"Video URL already queued for camera {camera_id}, skipping")
        return

    # Compute the destination filename (driven by recording start time, not now()),
    # then short-circuit if the file is already on disk. Ring-MQTT republishes the
    # event_select/attributes state topic periodically (and on reconnect), each
    # time with a freshly-signed URL pointing at the SAME underlying recording.
    # Without this check we'd re-download the same MP4 and re-register a new DB
    # row every ~10 minutes, producing the duplicate cards seen in the dashboard.
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    ts_dt = None
    if motion_time:
        try:
            ts_dt = datetime.fromisoformat(motion_time.replace('Z', '+00:00'))
            if ts_dt.tzinfo is not None:
                ts_dt = ts_dt.astimezone().replace(tzinfo=None)
        except (ValueError, TypeError):
            ts_dt = None
    if ts_dt is None:
        ts_dt = datetime.now()
    ts = ts_dt.strftime("%Y%m%d_%H%M%S")
    filename = f"recording_{ts}_{camera_id}.mp4"
    dest = RECORDINGS_DIR / filename

    if dest.exists() and dest.stat().st_size > 1000:
        logger.debug(f"Recording {filename} already on disk, skipping re-download/re-register")
        return

    # Download the MP4 immediately before the URL expires
    local_path = None
    try:
        response = requests.get(recording_url, timeout=60, allow_redirects=True)
        response.raise_for_status()

        if len(response.content) < 1000:
            logger.warning(f"Downloaded video too small ({len(response.content)} bytes), skipping")
            return

        # Write to a temp path first, then transmux to faststart so browsers can
        # start playback before the whole file is downloaded. Falls back to the
        # original file if ffmpeg is unavailable or the transmux fails.
        tmp_path = dest.with_suffix(".raw.mp4")
        tmp_path.write_bytes(response.content)
        try:
            import subprocess
            result = subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error",
                    "-i", str(tmp_path),
                    "-c", "copy",
                    "-movflags", "+faststart",
                    str(dest),
                ],
                capture_output=True, timeout=30,
            )
            if result.returncode == 0 and dest.exists() and dest.stat().st_size > 1000:
                tmp_path.unlink(missing_ok=True)
                logger.info(f"✓ Transmuxed video to faststart for progressive playback")
            else:
                logger.warning(
                    f"ffmpeg faststart failed (rc={result.returncode}); keeping original. "
                    f"stderr: {result.stderr.decode('utf-8', errors='ignore')[:200]}"
                )
                tmp_path.replace(dest)
        except FileNotFoundError:
            logger.warning("ffmpeg not available; keeping original (slow streaming)")
            tmp_path.replace(dest)
        except Exception as e:
            logger.warning(f"ffmpeg faststart error ({e}); keeping original")
            if tmp_path.exists():
                tmp_path.replace(dest)

        local_path = str(dest)
        logger.info(f"📹 Downloaded recording for camera {camera_id}: {len(response.content)} bytes → {filename}")
    except Exception as e:
        logger.error(f"Failed to download recording for camera {camera_id}: {e}")
        return
    
    # Register video in the Video Library (auto_ingested=True)
    video_id = None
    try:
        reg_response = requests.post(
            f"{CONFIG['BACKEND_API_URL']}/api/videos/register",
            json={
                "video_path": f"snapshots/recordings/{filename}",
                "camera_id": camera_id,
                "filename": filename
            },
            headers=get_api_headers(),
            timeout=10.0
        )
        if reg_response.status_code == 200:
            video_id = reg_response.json().get("video_id")
            logger.info(f"📹 Registered video in Video Library (id={video_id})")
        else:
            logger.warning(f"Failed to register video in library: HTTP {reg_response.status_code}")
    except Exception as e:
        logger.warning(f"Failed to register video in library: {e}")
    
    # Update the ring_event with the recording_url
    if ring_event_id:
        try:
            requests.patch(
                f"{CONFIG['BACKEND_API_URL']}/api/ring-events/{ring_event_id}",
                json={"recording_url": recording_url, "confidence": 0},  # include confidence to skip re-detection
                headers=get_api_headers(),
                timeout=5.0
            )
            logger.debug(f"Updated ring event #{ring_event_id} with recording_url")
        except Exception as e:
            logger.warning(f"Failed to update ring event #{ring_event_id} with recording_url: {e}")
    
    pending.append({
        "camera_id": camera_id,
        "url": recording_url,
        "local_path": local_path,
        "ring_event_id": ring_event_id,
        "queued_at": datetime.now().isoformat(),
        "motion_time": motion_time or datetime.now().isoformat()
    })
    save_pending_videos(pending)
    logger.info(f"📹 Queued video for deferred processing (camera {camera_id}, queue size: {len(pending)})")


async def fetch_settings_from_backend():
    """Fetch settings from backend API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CONFIG['BACKEND_API_URL']}/api/settings",
                headers=get_api_headers(),
                timeout=5.0
            )
            if response.status_code == 200:
                settings = response.json()
                # Update confidence threshold if changed
                new_threshold = settings.get('confidence_threshold')
                if new_threshold is not None:
                    old_threshold = CONFIG["CONFIDENCE_THRESHOLD"]
                    CONFIG["CONFIDENCE_THRESHOLD"] = float(new_threshold)
                    if old_threshold != CONFIG["CONFIDENCE_THRESHOLD"]:
                        logger.info(f"Updated confidence threshold from {old_threshold} to {CONFIG['CONFIDENCE_THRESHOLD']}")
                
                # Update enabled cameras (controls detection AND polling)
                new_cameras = settings.get('enabled_cameras')
                if new_cameras is not None:
                    old_cameras = CONFIG.get("ENABLED_CAMERAS", [])
                    CONFIG["ENABLED_CAMERAS"] = new_cameras
                    if old_cameras != CONFIG["ENABLED_CAMERAS"]:
                        logger.info(f"Updated enabled cameras from {old_cameras} to {CONFIG['ENABLED_CAMERAS']}")
                
                # Sync active hours from backend (frontend is source of truth)
                active_enabled = settings.get('active_hours_enabled')
                active_start = settings.get('active_hours_start')
                active_end = settings.get('active_hours_end')
                
                if active_enabled is not None:
                    old_enabled = CONFIG.get("ACTIVE_HOURS_ENABLED", True)
                    CONFIG["ACTIVE_HOURS_ENABLED"] = bool(active_enabled)
                    if old_enabled != CONFIG["ACTIVE_HOURS_ENABLED"]:
                        logger.info(f"Updated active_hours_enabled from {old_enabled} to {CONFIG['ACTIVE_HOURS_ENABLED']}")
                
                if active_start is not None:
                    old_start = CONFIG["ACTIVE_HOURS_START"]
                    CONFIG["ACTIVE_HOURS_START"] = int(active_start)
                    if old_start != CONFIG["ACTIVE_HOURS_START"]:
                        logger.info(f"Updated active_hours_start from {old_start} to {CONFIG['ACTIVE_HOURS_START']}")
                
                if active_end is not None:
                    old_end = CONFIG["ACTIVE_HOURS_END"]
                    CONFIG["ACTIVE_HOURS_END"] = int(active_end)
                    if old_end != CONFIG["ACTIVE_HOURS_END"]:
                        logger.info(f"Updated active_hours_end from {old_end} to {CONFIG['ACTIVE_HOURS_END']}")
                
                # Sync snapshot frequency (drives polling interval)
                new_freq = settings.get('snapshot_frequency')
                if new_freq is not None:
                    old_freq = CONFIG.get("SNAPSHOT_FREQUENCY", 60)
                    CONFIG["SNAPSHOT_FREQUENCY"] = int(new_freq)
                    if old_freq != CONFIG["SNAPSHOT_FREQUENCY"]:
                        logger.info(f"Updated snapshot_frequency from {old_freq}s to {CONFIG['SNAPSHOT_FREQUENCY']}s (polling interval: {CONFIG['SNAPSHOT_FREQUENCY'] + 10}s)")
                
                # Sync per-camera irrigation zone mapping
                new_zones = settings.get('camera_zones')
                if new_zones is not None:
                    old_zones = CONFIG.get("CAMERA_ZONES", {})
                    CONFIG["CAMERA_ZONES"] = new_zones
                    if old_zones != CONFIG["CAMERA_ZONES"]:
                        logger.info(f"Updated camera_zones: {CONFIG['CAMERA_ZONES']}")

                # Sync snapshot retention (days to keep no-deer periodic snapshots)
                new_retention = settings.get('snapshot_retention_days')
                if new_retention is not None:
                    try:
                        new_retention_int = max(1, int(new_retention))
                    except (TypeError, ValueError):
                        new_retention_int = None
                    if new_retention_int is not None:
                        old_retention = CONFIG.get("SNAPSHOT_RETENTION_DAYS", 3)
                        CONFIG["SNAPSHOT_RETENTION_DAYS"] = new_retention_int
                        if old_retention != new_retention_int:
                            logger.info(f"Updated snapshot_retention_days from {old_retention} to {new_retention_int}")
                
                # Sync irrigation duration (stored in seconds in backend)
                new_duration = settings.get('irrigation_duration')
                if new_duration is not None:
                    old_duration = CONFIG["RAINBIRD_DURATION_SECONDS"]
                    CONFIG["RAINBIRD_DURATION_SECONDS"] = int(new_duration)
                    if old_duration != CONFIG["RAINBIRD_DURATION_SECONDS"]:
                        logger.info(f"Updated irrigation_duration from {old_duration}s to {CONFIG['RAINBIRD_DURATION_SECONDS']}s")
                
                # Sync zone cooldown (stored in seconds in backend)
                new_cooldown = settings.get('zone_cooldown')
                if new_cooldown is not None:
                    old_cooldown = CONFIG["COOLDOWN_SECONDS"]
                    CONFIG["COOLDOWN_SECONDS"] = int(new_cooldown)
                    if old_cooldown != CONFIG["COOLDOWN_SECONDS"]:
                        logger.info(f"Updated cooldown from {old_cooldown}s to {CONFIG['COOLDOWN_SECONDS']}s")
                
                # Sync dry_run → ENABLE_IRRIGATION (dry_run=true means irrigation disabled)
                new_dry_run = settings.get('dry_run')
                if new_dry_run is not None:
                    old_enabled = CONFIG["ENABLE_IRRIGATION"]
                    CONFIG["ENABLE_IRRIGATION"] = not bool(new_dry_run)
                    if old_enabled != CONFIG["ENABLE_IRRIGATION"]:
                        logger.info(f"Updated ENABLE_IRRIGATION from {old_enabled} to {CONFIG['ENABLE_IRRIGATION']} (dry_run={new_dry_run})")
                
                return True
    except httpx.TimeoutException:
        logger.warning("Timeout fetching settings from backend")
    except Exception as e:
        logger.warning(f"Could not fetch settings from backend: {e}")
    return False


async def settings_refresh_loop():
    """Background task to periodically refresh settings from backend"""
    logger.info("Starting settings refresh loop")
    # Initial fetch
    await fetch_settings_from_backend()
    
    # Refresh every 30 seconds
    while True:
        await asyncio.sleep(30)
        await fetch_settings_from_backend()


def _hour_in_active_window(hour: int) -> bool:
    """Return True if the given hour-of-day falls inside the configured active window."""
    if not CONFIG.get("ACTIVE_HOURS_ENABLED", True):
        return True
    start = CONFIG["ACTIVE_HOURS_START"]
    end = CONFIG["ACTIVE_HOURS_END"]
    if start <= end:
        return start <= hour < end
    # Wraps midnight (e.g., 20:00 to 6:00)
    return hour >= start or hour < end


def is_active_hours() -> bool:
    """Check if current time is within active hours (synced from backend/frontend settings)"""
    return _hour_in_active_window(datetime.now().hour)


def _recording_within_active_hours(recording_time) -> bool:
    """Check if a recording's actual capture time falls within active hours.

    Used to gate motion-triggered video downloads, since Ring may deliver the
    event_select URL well after the configured active window. Falls back to the
    current-time check if recording_time is unavailable.
    """
    if not CONFIG.get("ACTIVE_HOURS_ENABLED", True):
        return True
    if recording_time is None:
        return is_active_hours()
    try:
        if isinstance(recording_time, datetime):
            hour = recording_time.hour
        else:
            hour = datetime.fromisoformat(str(recording_time)).hour
    except (ValueError, TypeError):
        return is_active_hours()
    return _hour_in_active_window(hour)


async def request_high_res_snapshot(camera_id: str) -> Optional[bytes]:
    """Request a fresh high-resolution snapshot from Ring via ring-mqtt"""
    try:
        # Ring-MQTT: set a short snapshot interval to trigger a fresh snapshot
        if mqtt_client and mqtt_client.is_connected():
            location_id = CONFIG.get("RING_LOCATION_ID", "")
            if not location_id:
                logger.warning("RING_LOCATION_ID not set, cannot request snapshot")
                return camera_snapshots.get(camera_id)
            
            # Clear cached snapshot to detect when a new one arrives
            old_snapshot = camera_snapshots.pop(camera_id, None)
            
            # Use snapshot_interval/command to request fresh snapshot (ring-mqtt topic)
            refresh_topic = f"ring/{location_id}/camera/{camera_id}/snapshot_interval/command"
            
            logger.info(f"Requesting high-res snapshot for camera {camera_id}...")
            mqtt_client.publish(refresh_topic, "10")
            
            # Wait up to 3 seconds for the new snapshot to arrive
            for i in range(30):  # 30 * 0.1s = 3 seconds
                await asyncio.sleep(0.1)
                if camera_id in camera_snapshots:
                    snapshot_bytes = camera_snapshots[camera_id]
                    # Check if it's reasonably sized (>50KB suggests high-res)
                    if len(snapshot_bytes) > 50000:
                        logger.info(f"✓ Received high-res snapshot: {len(snapshot_bytes)} bytes")
                        return snapshot_bytes
            
            # If we got here, we either got a low-res or no snapshot
            if camera_id in camera_snapshots:
                snapshot_bytes = camera_snapshots[camera_id]
                logger.warning(f"Snapshot may be low-res: {len(snapshot_bytes)} bytes")
                return snapshot_bytes
            else:
                logger.warning(f"No snapshot received after refresh request")
                return None
    except Exception as e:
        logger.error(f"Failed to request high-res snapshot: {e}")
        return None


async def download_snapshot(url: str) -> bytes:
    """Download image from URL"""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            logger.info(f"Downloaded snapshot: {len(response.content)} bytes")
            return response.content
    except Exception as e:
        logger.error(f"Failed to download snapshot: {e}")
        raise


async def detect_deer(image_bytes: bytes) -> Dict[str, Any]:
    """Send image to ML detector"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {"file": ("snapshot.jpg", image_bytes, "image/jpeg")}
            response = await client.post(
                f"{CONFIG['ML_DETECTOR_URL']}/detect",
                files=files
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"ML detection: {result['num_detections']} objects, deer={result['deer_detected']}")
            return result
    except Exception as e:
        logger.error(f"ML detection failed: {e}")
        raise


async def activate_rainbird(zone: str, duration: int) -> bool:
    """Activate Rainbird irrigation zone via pyrainbird library.
    
    Args:
        zone: Zone number as string (e.g. "1")
        duration: Duration in seconds
    """
    if not CONFIG["RAINBIRD_IP"]:
        logger.warning("Rainbird IP not configured, skipping activation")
        return False
    
    if not CONFIG["ENABLE_IRRIGATION"]:
        logger.info("Irrigation activation disabled (dry-run mode)")
        return False
    
    try:
        import aiohttp
        from pyrainbird import async_client
        
        zone_num = int(zone)
        # pyrainbird expects duration in minutes, minimum 1
        duration_minutes = max(1, round(duration / 60))
        
        logger.info(f"Activating Rainbird zone {zone_num} for {duration_minutes} min ({duration}s requested)")
        
        async with aiohttp.ClientSession() as session:
            controller = await async_client.create_controller(
                session,
                CONFIG["RAINBIRD_IP"],
                CONFIG["RAINBIRD_PASSWORD"]
            )
            await controller.irrigate_zone(zone_num, duration_minutes)
        
        logger.info(f"✓ Irrigation zone {zone_num} activated for {duration_minutes} min")
        return True
            
    except Exception as e:
        logger.error(f"Failed to activate irrigation: {e}")
        return False


async def stop_rainbird() -> bool:
    """Stop all Rainbird irrigation zones."""
    if not CONFIG["RAINBIRD_IP"]:
        logger.warning("Rainbird IP not configured")
        return False
    
    try:
        import aiohttp
        from pyrainbird import async_client
        
        logger.info("Stopping all irrigation zones")
        
        async with aiohttp.ClientSession() as session:
            controller = await async_client.create_controller(
                session,
                CONFIG["RAINBIRD_IP"],
                CONFIG["RAINBIRD_PASSWORD"]
            )
            await controller.stop_irrigation()
        
        logger.info("✓ All irrigation zones stopped")
        return True
            
    except Exception as e:
        logger.error(f"Failed to stop irrigation: {e}")
        return False


def log_ring_event(camera_id: str, event_type: str, snapshot_available: bool = False,
                   snapshot_size: int = None, snapshot_path: str = None, recording_url: str = None,
                   timestamp: str = None) -> Optional[int]:
    """Log Ring event to backend database for diagnostics (synchronous for MQTT thread)"""
    try:
        response = requests.post(
            f"{CONFIG['BACKEND_API_URL']}/api/ring-events",
            json={
                "camera_id": camera_id,
                "event_type": event_type,
                "timestamp": timestamp or datetime.now().isoformat(),
                "snapshot_available": snapshot_available,
                "snapshot_size": snapshot_size,
                "snapshot_path": snapshot_path,
                "recording_url": recording_url
            },
            headers=get_api_headers(),
            timeout=5.0
        )
        if response.status_code == 200:
            result = response.json()
            return result.get("event_id")
    except Exception as e:
        logger.error(f"Failed to log Ring event: {e}")
    return None


async def log_to_backend(event_data: Dict[str, Any]):
    """Log detection event to backend database"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"{CONFIG['BACKEND_API_URL']}/api/detections",
                json=event_data,
                headers=get_api_headers()
            )
            logger.info("Logged event to backend")
    except Exception as e:
        logger.error(f"Failed to log to backend: {e}")


async def record_chase_video(camera_id: str, ring_event_id: Optional[int]) -> None:
    """Record ~2 minutes of RTSP from a camera after a confirmed deer detection
    triggered irrigation. The resulting MP4 is registered in the Video Library
    with `triggering_event_id=ring_event_id` so the dashboard can link the
    snapshot card to the chase footage.

    Strategy:
      1. Try ffmpeg-direct against `rtsp://ring-mqtt:8554/{camera_id}_live`.
      2. If ffmpeg cannot connect within ~5s, publish stream/active=ON over MQTT
         (this asks ring-mqtt to start the live stream) and retry once.

    Per-camera lock (`chase_in_progress`) prevents overlapping recordings.
    """
    global chase_in_progress

    if chase_in_progress.get(camera_id, False):
        return
    chase_in_progress[camera_id] = True

    duration_seconds = 120  # 2-minute chase window
    rtsp_url = f"rtsp://ring-mqtt:8554/{camera_id}_live"

    try:
        RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        evt_part = ring_event_id if ring_event_id is not None else "noevt"
        filename = f"chase_{evt_part}_{camera_id}_{ts_str}.mp4"
        dest = RECORDINGS_DIR / filename
        tmp_path = dest.with_suffix(".raw.mp4")

        async def _run_ffmpeg() -> tuple[int, str]:
            """Run ffmpeg to capture `duration_seconds` of RTSP. Returns (rc, stderr)."""
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-loglevel", "error",
                "-rtsp_transport", "tcp",
                "-stimeout", "5000000",  # 5s socket timeout (microseconds)
                "-i", rtsp_url,
                "-t", str(duration_seconds),
                "-c", "copy",
                "-an",  # drop audio (Ring audio is often missing/garbled)
                str(tmp_path),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=duration_seconds + 30
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return -1, "ffmpeg watchdog timeout"
            return proc.returncode or 0, (stderr or b"").decode("utf-8", errors="ignore")

        logger.info(
            f"🎬 Starting chase recording for {camera_id} (event #{evt_part}) "
            f"→ {filename} ({duration_seconds}s)"
        )

        rc, err = await _run_ffmpeg()

        # Stream may not be live yet — ask ring-mqtt to start it and retry once.
        if (rc != 0 or not tmp_path.exists() or tmp_path.stat().st_size < 100_000) and CONFIG.get("RING_LOCATION_ID"):
            logger.warning(
                f"Chase recording first attempt failed for {camera_id} (rc={rc}); "
                f"requesting ring-mqtt to start live stream and retrying. stderr: {err[:200]}"
            )
            try:
                if mqtt_client is not None:
                    topic = f"ring/{CONFIG['RING_LOCATION_ID']}/camera/{camera_id}/stream/active/command"
                    mqtt_client.publish(topic, "ON", qos=0)
                    await asyncio.sleep(3.0)  # give ring-mqtt a moment to bring the stream up
            except Exception as e:
                logger.warning(f"Failed to publish stream/active for {camera_id}: {e}")
            tmp_path.unlink(missing_ok=True)
            rc, err = await _run_ffmpeg()

        if rc != 0 or not tmp_path.exists() or tmp_path.stat().st_size < 100_000:
            logger.error(
                f"Chase recording failed for {camera_id} (rc={rc}); "
                f"stderr: {err[:300]}"
            )
            tmp_path.unlink(missing_ok=True)
            return

        # Transmux to faststart for progressive browser playback (mirror existing pattern).
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(tmp_path),
                "-c", "copy",
                "-movflags", "+faststart",
                str(dest),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            _, fserr = await asyncio.wait_for(proc.communicate(), timeout=60)
            if proc.returncode == 0 and dest.exists() and dest.stat().st_size > 100_000:
                tmp_path.unlink(missing_ok=True)
            else:
                logger.warning(
                    f"Faststart transmux failed for chase recording (rc={proc.returncode}); "
                    f"keeping raw file. stderr: {(fserr or b'').decode('utf-8', errors='ignore')[:200]}"
                )
                tmp_path.replace(dest)
        except Exception as e:
            logger.warning(f"Faststart transmux error for chase recording: {e}; keeping raw file")
            if tmp_path.exists():
                tmp_path.replace(dest)

        size_mb = dest.stat().st_size / (1024 * 1024)
        logger.info(f"🎬 Chase recording saved: {filename} ({size_mb:.1f} MB)")

        # Register in Video Library with triggering_event_id so the dashboard can link it.
        try:
            reg_response = requests.post(
                f"{CONFIG['BACKEND_API_URL']}/api/videos/register",
                json={
                    "video_path": f"snapshots/recordings/{filename}",
                    "camera_id": camera_id,
                    "filename": filename,
                    "triggering_event_id": ring_event_id,
                },
                headers=get_api_headers(),
                timeout=10.0,
            )
            if reg_response.status_code == 200:
                video_id = reg_response.json().get("video_id")
                logger.info(f"🎬 Registered chase video in library (id={video_id}) for event #{evt_part}")
            else:
                logger.warning(
                    f"Failed to register chase video: HTTP {reg_response.status_code} {reg_response.text[:200]}"
                )
        except Exception as e:
            logger.error(f"Failed to register chase video in library: {e}")

    except Exception as e:
        logger.error(f"record_chase_video error for {camera_id}: {e}", exc_info=True)
    finally:
        chase_in_progress[camera_id] = False


async def process_camera_event(camera_id: str, timestamp: str, snapshot_bytes: bytes = None, snapshot_url: str = None, request_snapshot: bool = False, source: str = "unknown", ring_event_id: int = None):
    """Process a camera motion event"""
    global last_activation_time
    
    try:
        logger.info(f"Processing camera event: {camera_id} at {timestamp} (source: {source})")
        
        # Check if camera is enabled for detection
        enabled_cameras = CONFIG.get("ENABLED_CAMERAS", [])
        if enabled_cameras and camera_id not in enabled_cameras:
            logger.info(f"Camera {camera_id} not in enabled cameras list {enabled_cameras}, skipping detection")
            return
        
        # Check if within active hours
        if not is_active_hours():
            logger.info(f"Outside active hours ({CONFIG['ACTIVE_HOURS_START']}-{CONFIG['ACTIVE_HOURS_END']}), skipping")
            return
        
        # Get image bytes - prioritize high-res snapshot request
        if request_snapshot:
            # Request a fresh high-resolution snapshot
            logger.info(f"Requesting fresh high-resolution snapshot from Ring...")
            image_bytes = await request_high_res_snapshot(camera_id)
            
            if not image_bytes:
                logger.error(f"Failed to get high-res snapshot for camera {camera_id}")
                return
            
            # Save for debugging
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_path = Path(f"/app/snapshots/{ts}_{camera_id}_highres.jpg")
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_bytes(image_bytes)
            logger.info(f"Saved high-res snapshot: {snapshot_path} ({len(image_bytes)} bytes)")
            
        elif snapshot_bytes:
            # FAST PATH: Use cached snapshot from MQTT
            logger.info(f"✓ Using cached snapshot: {len(snapshot_bytes)} bytes")
            image_bytes = snapshot_bytes
            
            # Save for debugging
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            snapshot_path = Path(f"/app/snapshots/{ts}_{camera_id}.jpg")
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_bytes(image_bytes)
            
        elif snapshot_url:
            # SLOW PATH: Download and extract from video
            logger.info(f"Downloading from URL: {snapshot_url[:80]}...")
            media_bytes = await download_snapshot(snapshot_url)
            
            # Save media file temporarily
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_path = Path(f"/app/snapshots/{ts}_{camera_id}_temp")
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path.write_bytes(media_bytes)
            
            # Extract first frame if it's a video (MP4), otherwise use as-is
            snapshot_path = Path(f"/app/snapshots/{ts}_{camera_id}.jpg")
            if snapshot_url.lower().endswith('.mp4'):
                logger.info(f"Extracting frame from MP4 video...")
                import subprocess
                result = subprocess.run([
                    'ffmpeg', '-i', str(temp_path), 
                    '-vframes', '1', '-f', 'image2',
                    '-y', str(snapshot_path)
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"FFmpeg failed: {result.stderr}")
                    temp_path.unlink()
                    return
                
                temp_path.unlink()  # Clean up temp file
                logger.info(f"Extracted frame: {snapshot_path}")
            else:
                # Already an image, just rename
                temp_path.rename(snapshot_path)
                logger.info(f"Saved snapshot: {snapshot_path}")
            
            # Read the image for ML detection
            image_bytes = snapshot_path.read_bytes()
        else:
            logger.error("No snapshot_bytes or snapshot_url provided!")
            return
        
        # Run ML detection
        detection_result = await detect_deer(image_bytes)
        
        # Check if deer detected
        deer_detected = detection_result.get("deer_detected", False)
        confidence = 0.0
        
        if deer_detected and detection_result.get("detections"):
            # Get highest confidence deer detection (only actual deer class)
            deer_detections = [
                d for d in detection_result["detections"]
                if d["class"].lower() == 'deer'
            ]
            if deer_detections:
                confidence = max(d["confidence"] for d in deer_detections)
        
        logger.info(f"Detection result: deer={deer_detected}, confidence={confidence:.2f}")
        
        # Prepare event data
        event_data = {
            "timestamp": timestamp,
            "camera_id": camera_id,
            "deer_detected": deer_detected,
            "confidence": confidence,
            "snapshot_path": str(snapshot_path),
            "detections": detection_result.get("detections", []),
            "irrigation_activated": False
        }
        
        # If deer detected, check cooldown and activate irrigation
        if deer_detected:
            now = datetime.now()

            # Build chase chain from per-camera config (list of zones to fire in order).
            try:
                fallback_zone = int(CONFIG["RAINBIRD_ZONE"])
            except (TypeError, ValueError):
                fallback_zone = None
            chain = build_chase_chain(camera_id, fallback_zone)
            duration = CONFIG["RAINBIRD_DURATION_SECONDS"]
            chain_total = duration * len(chain) if chain else duration

            # Check cooldown — must cover full chase chain so zones don't overlap with a re-trigger
            if last_activation_time:
                user_cooldown = CONFIG["COOLDOWN_SECONDS"]
                effective_cooldown = max(user_cooldown, chain_total)
                elapsed = (now - last_activation_time).total_seconds()
                if elapsed < effective_cooldown:
                    if user_cooldown < chain_total:
                        logger.warning(
                            f"⚠ Detection suppressed: chain-duration floor cooldown active "
                            f"({elapsed:.0f}s/{effective_cooldown}s; user setting={user_cooldown}s, "
                            f"chain={chain} → {chain_total}s)"
                        )
                    else:
                        logger.info(f"Cooldown active: {elapsed:.0f}s/{effective_cooldown}s")
                else:
                    last_activation_time = None  # Cooldown expired, allow activation

            if last_activation_time is None and chain:
                logger.info(f"Camera {camera_id} → chase chain {chain}")
                # Fire first zone synchronously so we know if it succeeded; rest run in background
                first_ok = await activate_rainbird(str(chain[0]), duration)
                if first_ok and len(chain) > 1:
                    asyncio.create_task(run_chase(chain[1:], duration))
                if first_ok:
                    last_activation_time = now
                    event_data["irrigation_activated"] = True
                    logger.info("✓✓✓ DEER DETERRENT ACTIVATED ✓✓✓")
                    # Kick off a 2-minute RTSP "chase" recording for this camera, linked back to the
                    # ring_event whose detection triggered it. Per-camera lock prevents overlapping
                    # chase recordings if the same camera re-fires inside the cooldown.
                    if not chase_in_progress.get(camera_id, False):
                        asyncio.create_task(record_chase_video(camera_id, ring_event_id))
                    else:
                        logger.info(f"Chase recording already in progress for {camera_id}; skipping")
        
        # Update Ring event with detection result (including bboxes and irrigation status)
        if ring_event_id:
            try:
                update_payload = {
                    "processed": True,
                    "deer_detected": deer_detected,
                    "confidence": confidence,
                    "detection_bboxes": detection_result.get("detections", []) if deer_detected else [],
                    "model_version": detection_result.get("model_version", "unknown"),
                    "irrigation_activated": event_data["irrigation_activated"]
                }
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.patch(
                        f"{CONFIG['BACKEND_API_URL']}/api/ring-events/{ring_event_id}",
                        json=update_payload,
                        headers=get_api_headers()
                    )
            except Exception as e:
                logger.error(f"Failed to update Ring event: {e}")
        
        # Log to backend
        await log_to_backend(event_data)
        
    except Exception as e:
        logger.error(f"Error processing camera event: {e}", exc_info=True)


async def process_video_frames(camera_id: str, recording_url: str, motion_time: str = None, local_path: str = None):
    """Extract frames from a Ring motion video and run ML detection on each.
    
    If local_path is provided, uses the already-downloaded file.
    Otherwise downloads from recording_url (may fail if URL has expired).
    
    Extracts frames at the configured snapshot_frequency cadence, runs ML detection
    on each, and logs results as ring_events with event_type='video_frame'.
    No irrigation is triggered from video frames — this is purely for model improvement.
    
    Args:
        camera_id: Ring camera ID
        recording_url: Original Ring recording URL (stored in DB for reference)
        motion_time: ISO timestamp of the original motion event (used for frame timestamps)
        local_path: Path to already-downloaded MP4 file (preferred over downloading)
    """
    import subprocess
    
    temp_video = None  # Track temp file for cleanup in finally
    
    try:
        # Use original motion event time for timestamps, fall back to now
        if motion_time:
            try:
                event_time = datetime.fromisoformat(motion_time)
            except (ValueError, TypeError):
                logger.warning(f"Invalid motion_time '{motion_time}', using current time")
                event_time = datetime.now()
        else:
            event_time = datetime.now()
        now = datetime.now()
        
        # Use local file if already downloaded, otherwise download from URL
        if local_path and Path(local_path).exists():
            temp_video = Path(local_path)
            logger.info(f"📹 Using pre-downloaded video for camera {camera_id}: {temp_video.name} ({temp_video.stat().st_size} bytes)")
        else:
            logger.info(f"📹 Downloading motion video for camera {camera_id}: {recording_url[:80]}...")
            
            # Download the MP4 file
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                response = await client.get(recording_url)
                response.raise_for_status()
                video_bytes = response.content
            
            if len(video_bytes) < 1000:
                logger.warning(f"Video too small ({len(video_bytes)} bytes), likely invalid — skipping")
                return
            
            logger.info(f"Downloaded video: {len(video_bytes)} bytes")
            
            # Save video to temp file (use event_time for naming)
        ts = event_time.strftime("%Y%m%d_%H%M%S")
        temp_video = Path(f"/app/snapshots/video_{ts}_{camera_id}.mp4")
        temp_video.parent.mkdir(parents=True, exist_ok=True)
        temp_video.write_bytes(video_bytes)
        
        # Get video duration and fps via ffprobe
        probe_result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', str(temp_video)
        ], capture_output=True, text=True)
        
        duration = 0.0
        fps = 15.0
        if probe_result.returncode == 0:
            try:
                probe_data = json.loads(probe_result.stdout)
                duration = float(probe_data.get('format', {}).get('duration', 0))
                for stream in probe_data.get('streams', []):
                    if stream.get('codec_type') == 'video':
                        # Parse fps from r_frame_rate (e.g., "15/1")
                        r_fps = stream.get('r_frame_rate', '15/1')
                        if '/' in r_fps:
                            num, den = r_fps.split('/')
                            fps = float(num) / float(den) if float(den) > 0 else 15.0
                        else:
                            fps = float(r_fps)
                        break
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logger.warning(f"Failed to parse ffprobe output: {e}")
        
        if duration <= 0:
            logger.warning(f"Could not determine video duration, cleaning up")
            temp_video.unlink(missing_ok=True)
            return
        
        logger.info(f"Video info: duration={duration:.1f}s, fps={fps:.1f}")
        
        # Determine frame extraction cadence from snapshot_frequency setting
        cadence = max(CONFIG.get("SNAPSHOT_FREQUENCY", 60), 10)  # At least every 10s
        
        # Calculate frame extraction times (seconds into the video)
        # Always extract the first frame at t=2s (skip initial black frames)
        extract_times = [2.0]
        t = 2.0 + cadence
        while t < duration - 1:
            extract_times.append(t)
            t += cadence
        
        # Also extract a frame at the midpoint if cadence is very long relative to video
        if cadence >= duration and duration > 5:
            mid = duration / 2
            if mid not in extract_times:
                extract_times.append(mid)
                extract_times.sort()
        
        logger.info(f"Extracting {len(extract_times)} frames at cadence={cadence}s from {duration:.1f}s video")
        
        frames_processed = 0
        deer_found = 0
        
        for frame_time in extract_times:
            try:
                # Extract single frame at specific timestamp using ffmpeg
                frame_filename = f"video_{ts}_{camera_id}_f{frame_time:.0f}.jpg"
                frame_path = Path(f"/app/snapshots/{frame_filename}")
                frame_path.parent.mkdir(parents=True, exist_ok=True)
                
                extract_result = subprocess.run([
                    'ffmpeg', '-ss', str(frame_time),
                    '-i', str(temp_video),
                    '-vframes', '1', '-q:v', '2',
                    '-y', str(frame_path)
                ], capture_output=True, text=True, timeout=15)
                
                if extract_result.returncode != 0 or not frame_path.exists():
                    logger.warning(f"Failed to extract frame at t={frame_time:.1f}s: {extract_result.stderr[:200]}")
                    continue
                
                frame_bytes = frame_path.read_bytes()
                if len(frame_bytes) < 500:
                    logger.warning(f"Extracted frame too small ({len(frame_bytes)} bytes) at t={frame_time:.1f}s, skipping")
                    frame_path.unlink(missing_ok=True)
                    continue
                
                # Compute frame timestamp: original motion time + frame offset into video
                frame_timestamp = event_time + timedelta(seconds=frame_time)
                
                # Log ring event for this frame (use computed timestamp from motion event)
                snapshot_rel_path = f"snapshots/{frame_filename}"
                ring_event_id = log_ring_event(
                    camera_id=camera_id,
                    event_type="video_frame",
                    snapshot_available=True,
                    snapshot_size=len(frame_bytes),
                    snapshot_path=snapshot_rel_path,
                    recording_url=recording_url,
                    timestamp=frame_timestamp.isoformat()
                )
                
                if not ring_event_id:
                    logger.error(f"Failed to log ring event for video frame at t={frame_time:.1f}s")
                    continue
                
                # Run ML detection
                detection_result = await detect_deer(frame_bytes)
                
                deer_detected = detection_result.get("deer_detected", False)
                confidence = 0.0
                if deer_detected and detection_result.get("detections"):
                    deer_detections = [
                        d for d in detection_result["detections"]
                        if d["class"].lower() == 'deer'
                    ]
                    if deer_detections:
                        confidence = max(d["confidence"] for d in deer_detections)
                
                # Update ring event with detection results (same as periodic snapshots)
                try:
                    update_payload = {
                        "processed": True,
                        "deer_detected": deer_detected,
                        "confidence": confidence,
                        "detection_bboxes": detection_result.get("detections", []) if deer_detected else [],
                        "model_version": detection_result.get("model_version", "unknown")
                    }
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        await client.patch(
                            f"{CONFIG['BACKEND_API_URL']}/api/ring-events/{ring_event_id}",
                            json=update_payload,
                            headers=get_api_headers()
                        )
                except Exception as e:
                    logger.error(f"Failed to update ring event #{ring_event_id}: {e}")
                
                frames_processed += 1
                if deer_detected:
                    deer_found += 1
                    logger.info(f"🦌 Deer detected in video frame at t={frame_time:.1f}s (confidence={confidence:.2f})")
                else:
                    logger.debug(f"No deer in video frame at t={frame_time:.1f}s")
                
            except subprocess.TimeoutExpired:
                logger.warning(f"ffmpeg timed out extracting frame at t={frame_time:.1f}s")
            except Exception as e:
                logger.error(f"Error processing video frame at t={frame_time:.1f}s: {e}")
        
        # Clean up temp video file
        temp_video.unlink(missing_ok=True)
        
        logger.info(f"📹 Video frame extraction complete: {frames_processed} frames processed, {deer_found} with deer")
        
    except httpx.TimeoutException:
        logger.error(f"Timeout downloading video for camera {camera_id}")
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error downloading video for camera {camera_id}: {e.response.status_code}")
    except Exception as e:
        logger.error(f"Error in video frame extraction for camera {camera_id}: {e}", exc_info=True)
    finally:
        # Clean up temp file if it still exists
        if temp_video is not None:
            try:
                temp_video.unlink(missing_ok=True)
            except Exception:
                pass


def on_mqtt_connect(client, userdata, flags, rc):
    """MQTT connection callback"""
    logger.info(f"MQTT on_connect callback fired with rc={rc}")
    if rc == 0:
        logger.info("✓ MQTT broker connection established in callback")
        # Subscribe to Ring camera motion events (Ring-MQTT v5.x format)
        topics = [
            ("ring/#", 0),  # Subscribe to ALL Ring topics for debugging
            ("ring/+/camera/+/event_select/attributes", 0),
            ("ring/+/camera/+/motion", 0),
            ("ring/+/camera/+/ding", 0),
        ]
        result = client.subscribe(topics)
        logger.info(f"✓ Subscribed to Ring motion topics with result: {result}")
        logger.info(f"  Topics: {[t[0] for t in topics]}")
    else:
        logger.error(f"MQTT connection failed with code {rc}")


def on_mqtt_message(client, userdata, msg):
    """MQTT message callback"""
    try:
        topic = msg.topic
        parts = topic.split('/')
        
        # Extract location_id from topic if not yet configured
        if not CONFIG["RING_LOCATION_ID"] and len(parts) >= 2 and parts[0] == "ring":
            CONFIG["RING_LOCATION_ID"] = parts[1]
            logger.info(f"Detected Ring location ID: {CONFIG['RING_LOCATION_ID']}")
        
        # Handle binary snapshot images - store them for instant access
        if len(parts) >= 6 and parts[0] == "ring" and parts[2] == "camera" and parts[4] == "snapshot" and parts[5] == "image":
            camera_id = parts[3]
            camera_snapshots[camera_id] = msg.payload
            logger.debug(f"Cached snapshot for camera {camera_id}: {len(msg.payload)} bytes")
            return
        
        # Try to decode text messages
        try:
            payload = msg.payload.decode()
        except UnicodeDecodeError:
            # Unknown binary message, skip
            return
        
        # Handle motion/state messages (INSTANT - 1-2 seconds after motion)
        if len(parts) >= 6 and parts[0] == "ring" and parts[2] == "camera" and parts[4] == "motion" and parts[5] == "state":
            camera_id = parts[3]
            
            if payload.upper() == "ON":
                logger.info(f"⚡ INSTANT motion detected on camera {camera_id}")
                
                # Skip cameras not in enabled list
                enabled_cameras = CONFIG.get("ENABLED_CAMERAS", [])
                if enabled_cameras and camera_id not in enabled_cameras:
                    logger.debug(f"Camera {camera_id} not enabled, skipping motion event")
                    return
                
                # Log Ring event if within active hours (synchronous call)
                ring_event_id = None
                snapshot_path = None
                if is_active_hours():
                    snapshot_available = camera_id in camera_snapshots
                    snapshot_size = len(camera_snapshots[camera_id]) if snapshot_available else None
                    
                    # Save snapshot to disk for later analysis/testing
                    if snapshot_available:
                        try:
                            from pathlib import Path
                            snapshot_dir = Path("/app/snapshots")
                            snapshot_dir.mkdir(parents=True, exist_ok=True)
                            
                            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                            snapshot_filename = f"event_{timestamp_str}_{camera_id}_snapshot.jpg"
                            snapshot_path_obj = snapshot_dir / snapshot_filename
                            snapshot_path_obj.write_bytes(camera_snapshots[camera_id])
                            snapshot_path = f"snapshots/{snapshot_filename}"
                            
                            logger.info(f"✓ Saved snapshot to {snapshot_path}")
                        except Exception as e:
                            logger.error(f"Failed to save snapshot: {e}")
                            snapshot_path = None
                    
                    # Call synchronous logging function (runs in MQTT thread)
                    ring_event_id = log_ring_event(
                        camera_id=camera_id,
                        event_type="motion",
                        snapshot_available=snapshot_available,
                        snapshot_size=snapshot_size,
                        snapshot_path=snapshot_path
                    )
                    if ring_event_id:
                        logger.info(f"Logged Ring event #{ring_event_id}")
                        last_motion_ring_event[camera_id] = ring_event_id
                    
                    # Use instant snapshot for real-time detection (low-res but fast)
                    if camera_id in camera_snapshots:
                        # Update snapshot hash so periodic poller skips this same image
                        motion_hash = hashlib.md5(camera_snapshots[camera_id]).hexdigest()
                        last_snapshot_hash[camera_id] = motion_hash
                        logger.info(f"✓ Using instant snapshot for real-time detection")
                        event_queue.put((0, next(event_counter), {  # Priority 0 = highest (motion events)
                            "camera_id": camera_id,
                            "snapshot_bytes": camera_snapshots[camera_id],
                            "timestamp": datetime.now().isoformat(),
                            "source": "instant_snapshot",
                            "ring_event_id": ring_event_id
                        }))
                    else:
                        logger.warning(f"No cached snapshot available for {camera_id}")
                else:
                    logger.info(f"Outside active hours ({CONFIG['ACTIVE_HOURS_START']}-{CONFIG['ACTIVE_HOURS_END']}), skipping motion event")
            return
        
        # Handle event_select messages — queue video URLs for deferred processing
        if "event_select" in topic and len(parts) >= 6 and parts[4] == "event_select":
            camera_id = parts[3]
            
            # Only queue for enabled cameras
            enabled_cameras = CONFIG.get("ENABLED_CAMERAS", [])
            if enabled_cameras and camera_id not in enabled_cameras:
                logger.debug(f"Camera {camera_id} not enabled, skipping video queuing")
                return
            
            try:
                payload_json = json.loads(payload)
                logger.info(f"📹 event_select payload for camera {camera_id}: {json.dumps(payload_json)[:500]}")
                # Ring-MQTT event_select/attributes payload contains recording URL
                recording_url = None
                
                # Try common ring-mqtt payload structures
                if isinstance(payload_json, dict):
                    recording_url = (
                        payload_json.get("recordingUrl") or
                        payload_json.get("recording_url") or
                        payload_json.get("recording", {}).get("url") or
                        payload_json.get("videoUrl") or
                        payload_json.get("ding_url") or
                        payload_json.get("url")
                    )
                
                if recording_url and '.mp4' in recording_url.lower():
                    recording_time = extract_recording_time_from_url(recording_url)
                    if recording_time:
                        logger.info(f"📹 Extracted recording time from URL for camera {camera_id}: {recording_time}")
                    if not _recording_within_active_hours(recording_time):
                        logger.info(f"📹 Skipping video for camera {camera_id} — recording time {recording_time} is outside active hours ({CONFIG['ACTIVE_HOURS_START']}-{CONFIG['ACTIVE_HOURS_END']})")
                        return
                    event_id = last_motion_ring_event.get(camera_id)
                    queue_video_for_processing(camera_id, recording_url, motion_time=recording_time or datetime.now().isoformat(), ring_event_id=event_id)
                elif recording_url:
                    logger.info(f"event_select URL is not MP4 for camera {camera_id}: {recording_url[:120]}")
                else:
                    logger.info(f"No recording URL found in event_select payload for camera {camera_id}")
            except (json.JSONDecodeError, TypeError) as e:
                # Payload might be a direct URL string
                if payload and '.mp4' in payload.lower() and payload.startswith('http'):
                    recording_time = extract_recording_time_from_url(payload)
                    if not _recording_within_active_hours(recording_time):
                        logger.info(f"📹 Skipping video for camera {camera_id} — recording time {recording_time} is outside active hours ({CONFIG['ACTIVE_HOURS_START']}-{CONFIG['ACTIVE_HOURS_END']})")
                        return
                    event_id = last_motion_ring_event.get(camera_id)
                    queue_video_for_processing(camera_id, payload, motion_time=recording_time or datetime.now().isoformat(), ring_event_id=event_id)
                else:
                    logger.warning(f"Could not parse event_select payload: {e} — raw: {payload[:200]}")
            return
        
    except Exception as e:
        logger.error(f"Error processing MQTT message: {e}", exc_info=True)


def setup_mqtt():
    """Setup MQTT client"""
    global mqtt_client
    
    try:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_message = on_mqtt_message
        
        if CONFIG["MQTT_USER"]:
            mqtt_client.username_pw_set(CONFIG["MQTT_USER"], CONFIG["MQTT_PASSWORD"])
        
        logger.info(f"Connecting to MQTT broker at {CONFIG['MQTT_HOST']}:{CONFIG['MQTT_PORT']}")
        mqtt_client.connect(CONFIG["MQTT_HOST"], CONFIG["MQTT_PORT"], 60)
        mqtt_client.loop_start()
        
        logger.info(f"MQTT client loop started (waiting for on_connect callback...)")
        
    except Exception as e:
        logger.error(f"Failed to setup MQTT: {e}")


async def process_event_queue():
    """Background task to process events from MQTT queue"""
    logger.info("Event queue processor started")
    
    while True:
        try:
            # Check queue for events (non-blocking)
            try:
                priority, _counter, event = event_queue.get_nowait()  # Get tuple (priority, counter, event)
                source = event.get("source", "unknown")
                logger.info(f"Processing queued event for camera {event['camera_id']} (priority={priority}, source={source})")
                
                # Process the event with either cached snapshot or URL
                await process_camera_event(
                    camera_id=event["camera_id"],
                    timestamp=event["timestamp"],
                    snapshot_bytes=event.get("snapshot_bytes"),
                    snapshot_url=event.get("snapshot_url"),
                    request_snapshot=event.get("request_snapshot", False),
                    source=event.get("source", "unknown"),
                    ring_event_id=event.get("ring_event_id")
                )
                
                event_queue.task_done()
                
            except queue.Empty:
                # No events in queue, sleep briefly
                await asyncio.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Error in event queue processor: {e}", exc_info=True)
            await asyncio.sleep(1)


async def periodic_snapshot_poller():
    """Request snapshots from configured cameras at regular intervals"""
    logger.info("Periodic snapshot poller started")
    
    if not CONFIG["ENABLE_PERIODIC_SNAPSHOTS"]:
        logger.info("Periodic snapshots disabled, poller exiting")
        return
    
    if not CONFIG["RING_LOCATION_ID"]:
        logger.error("RING_LOCATION_ID not configured, periodic snapshots disabled")
        return
    
    polling_interval = CONFIG["SNAPSHOT_FREQUENCY"] + 10
    logger.info(f"Periodic snapshots enabled for cameras: {CONFIG['ENABLED_CAMERAS']} (snapshot frequency: {CONFIG['SNAPSHOT_FREQUENCY']}s, polling every {polling_interval}s, active hours: {CONFIG['ACTIVE_HOURS_START']}:00-{CONFIG['ACTIVE_HOURS_END']}:00)")
    
    # Subscribe to snapshot response topics for enabled cameras
    subscribed_cameras = set()
    for camera_id in CONFIG["ENABLED_CAMERAS"]:
        topic = f"ring/{CONFIG['RING_LOCATION_ID']}/camera/{camera_id}/snapshot/image"
        mqtt_client.subscribe(topic)
        subscribed_cameras.add(camera_id)
        logger.info(f"Subscribed to periodic snapshots: {topic}")
    
    while True:
        try:
            # Poll interval = snapshot_frequency + 10s buffer (dynamically updated via settings sync)
            poll_interval = CONFIG["SNAPSHOT_FREQUENCY"] + 10
            await asyncio.sleep(poll_interval)
            
            if not is_active_hours():
                logger.debug("Outside active hours, skipping periodic snapshots")
                continue
            
            # Re-subscribe if enabled cameras changed
            current_enabled = set(CONFIG.get("ENABLED_CAMERAS", []))
            if current_enabled != subscribed_cameras:
                # Unsubscribe removed cameras
                for cam in subscribed_cameras - current_enabled:
                    topic = f"ring/{CONFIG['RING_LOCATION_ID']}/camera/{cam}/snapshot/image"
                    mqtt_client.unsubscribe(topic)
                    logger.info(f"Unsubscribed from removed camera: {topic}")
                # Subscribe new cameras
                for cam in current_enabled - subscribed_cameras:
                    topic = f"ring/{CONFIG['RING_LOCATION_ID']}/camera/{cam}/snapshot/image"
                    mqtt_client.subscribe(topic)
                    logger.info(f"Subscribed to new camera: {topic}")
                subscribed_cameras = current_enabled
                logger.info(f"Updated polling cameras to: {subscribed_cameras}")
            
            for camera_id in CONFIG["ENABLED_CAMERAS"]:
                # Request snapshot refresh via MQTT (ring-mqtt updates its interval)
                topic = f"ring/{CONFIG['RING_LOCATION_ID']}/camera/{camera_id}/snapshot_interval/command"
                mqtt_client.publish(topic, "10")
                
            # Wait for all cameras to potentially deliver fresh snapshots
            await asyncio.sleep(8)
            
            for camera_id in CONFIG["ENABLED_CAMERAS"]:
                # Use whatever snapshot is currently cached from the MQTT stream
                # Ring-mqtt publishes snapshots every ~10s, so camera_snapshots
                # should always have recent data if MQTT is connected
                if camera_id not in camera_snapshots:
                    logger.warning(f"No cached snapshot for camera {camera_id}")
                    continue
                
                snapshot_bytes = camera_snapshots[camera_id]
                
                # Check if this is the same snapshot as last time (prevent duplicates)
                snapshot_hash = hashlib.md5(snapshot_bytes).hexdigest()
                
                if camera_id in last_snapshot_hash and last_snapshot_hash[camera_id] == snapshot_hash:
                    logger.debug(f"Skipping duplicate snapshot for camera {camera_id} (same hash)")
                    continue
                
                # Update hash tracker
                last_snapshot_hash[camera_id] = snapshot_hash
                
                # Log Ring event (synchronous)
                snapshot_size = len(snapshot_bytes)
                
                # Save snapshot to disk
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                snapshot_filename = f"periodic_{timestamp_str}_{camera_id}.jpg"
                snapshot_path_obj = Path(f"/app/snapshots/{snapshot_filename}")
                snapshot_path_obj.parent.mkdir(parents=True, exist_ok=True)
                snapshot_path_obj.write_bytes(snapshot_bytes)
                snapshot_path = f"snapshots/{snapshot_filename}"
                
                logger.info(f"✓ Saved periodic snapshot to {snapshot_path} ({snapshot_size} bytes)")
                
                ring_event_id = log_ring_event(
                    camera_id=camera_id,
                    event_type="periodic_snapshot",
                    snapshot_available=True,
                    snapshot_size=snapshot_size,
                    snapshot_path=snapshot_path
                )
                
                if ring_event_id:
                    logger.info(f"Logged periodic snapshot event #{ring_event_id}")
                
                # Queue for ML detection (lower priority than motion events)
                event_queue.put((1, next(event_counter), {  # Priority 1 = lower (periodic snapshots)
                    "camera_id": camera_id,
                    "snapshot_bytes": snapshot_bytes,
                    "timestamp": datetime.now().isoformat(),
                    "source": "periodic_snapshot",
                    "ring_event_id": ring_event_id
                }))
                
                last_periodic_snapshot_time[camera_id] = datetime.now()
        
        except Exception as e:
            logger.error(f"Error in periodic snapshot poller: {e}", exc_info=True)
            await asyncio.sleep(60)


async def cleanup_no_deer_snapshots():
    """Delete no-deer periodic snapshots and old recordings/videos.

    Runs immediately at startup, then hourly. Recording/video retention is
    derived from SNAPSHOT_RETENTION_DAYS (max 7 days) so a single setting
    governs all on-disk cleanup.
    """
    logger.info("Snapshot cleanup task started (runs once at startup, then hourly)")

    first_run = True
    while True:
        try:
            if first_run:
                first_run = False
            else:
                # Run every hour after the initial pass
                await asyncio.sleep(3600)

            # Calculate cutoff time from configured retention (synced from backend settings)
            retention_days = max(1, int(CONFIG.get("SNAPSHOT_RETENTION_DAYS", 3)))
            cutoff = datetime.now() - timedelta(days=retention_days)

            # Recordings/videos use a 7-day cap (or the snapshot retention if longer)
            recording_retention_days = max(retention_days, 7)
            recording_cutoff = datetime.now() - timedelta(days=recording_retention_days)
            
            # Call backend API to delete old no-deer periodic snapshots
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{CONFIG['BACKEND_API_URL']}/api/cleanup-old-snapshots",
                    json={
                        "event_type": "periodic_snapshot",
                        "deer_detected": False,
                        "older_than": cutoff.isoformat()
                    },
                    headers=get_api_headers()
                )
                
                if response.status_code == 200:
                    result = response.json()
                    deleted_count = result.get("deleted", 0)
                    if deleted_count > 0:
                        logger.info(f"Cleaned up {deleted_count} old no-deer periodic snapshots (>{retention_days} days)")
                else:
                    logger.warning(f"Cleanup request failed: HTTP {response.status_code}")
            
            # Clean up old downloaded recordings — delete MP4 files
            # but keep video entries in DB so frames/annotations are preserved
            try:
                if RECORDINGS_DIR.exists():
                    deleted_recordings = 0
                    for f in RECORDINGS_DIR.glob("*.mp4"):
                        if datetime.fromtimestamp(f.stat().st_mtime) < recording_cutoff:
                            f.unlink()
                            deleted_recordings += 1
                    if deleted_recordings:
                        logger.info(f"Cleaned up {deleted_recordings} old recording files (>{recording_retention_days} days)")
            except Exception as e:
                logger.warning(f"Error cleaning up old recordings: {e}")
            
            # Clean up old video files via backend (both manual + auto-ingested)
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.delete(
                        f"{CONFIG['BACKEND_API_URL']}/api/videos/cleanup-old",
                        params={"days": recording_retention_days},
                        headers=get_api_headers()
                    )
                    if resp.status_code == 200:
                        result = resp.json()
                        if result.get("deleted", 0) > 0:
                            logger.info(f"Cleaned up {result['deleted']} old video files, freed {result['freed_mb']} MB")
            except Exception as e:
                logger.warning(f"Error calling video cleanup API: {e}")
        
        except Exception as e:
            logger.error(f"Error in snapshot cleanup task: {e}", exc_info=True)


async def video_batch_processor():
    """Process queued videos whenever we are outside active hours.

    Triggers whenever there are pending videos AND we are currently inactive.
    Previously this required a live active→inactive transition, which meant a
    coordinator restart during the day would silently strand the queue until
    the next day's transition. This version drains opportunistically and is
    idempotent (the queue is cleared after each successful drain).
    """
    logger.info("Video batch processor started")

    while True:
        try:
            await asyncio.sleep(60)  # Check every minute

            currently_active = is_active_hours()

            if not currently_active:
                # Outside active hours — drain whatever is queued (if anything)
                pending = load_pending_videos()
                # Dedupe by local_path: Ring-MQTT can republish the same recording
                # multiple times; we only need to process the underlying file once.
                seen_paths = set()
                deduped = []
                for entry in pending:
                    lp = entry.get("local_path") or entry.get("url")
                    if lp in seen_paths:
                        continue
                    seen_paths.add(lp)
                    deduped.append(entry)
                if len(deduped) != len(pending):
                    logger.info(
                        f"🎬 Pending queue deduped {len(pending)} → {len(deduped)} (same file republished)"
                    )
                pending = deduped
                if pending:
                    # Filter to only videos from active monitoring hours
                    start_h = CONFIG.get("ACTIVE_HOURS_START", 20)
                    end_h = CONFIG.get("ACTIVE_HOURS_END", 6)
                    valid = []
                    skipped = 0
                    for entry in pending:
                        mt = entry.get("motion_time", entry.get("queued_at", ""))
                        try:
                            mt_dt = datetime.fromisoformat(mt)
                            h = mt_dt.hour
                            if start_h <= end_h:
                                in_active = start_h <= h < end_h
                            else:
                                in_active = h >= start_h or h < end_h
                            if in_active:
                                valid.append(entry)
                            else:
                                skipped += 1
                                logger.info(f"Skipping video from {mt} — outside active hours ({start_h}:00-{end_h}:00)")
                        except (ValueError, TypeError):
                            valid.append(entry)  # Can't parse time, process anyway
                    if skipped:
                        logger.info(f"🎬 Filtered {skipped}/{len(pending)} videos outside active hours")
                    logger.info(f"🎬 Active hours ended — processing {len(valid)} queued videos")
                    processed = 0
                    fp_skipped = 0
                    for entry in valid:
                        cam = entry.get("camera_id", "unknown")
                        url = entry.get("url", "")
                        mt = entry.get("motion_time")
                        lp = entry.get("local_path")
                        eid = entry.get("ring_event_id")
                        
                        # Check if the associated snapshot was marked as false positive
                        if eid:
                            try:
                                async with httpx.AsyncClient(timeout=5.0) as client:
                                    resp = await client.get(
                                        f"{CONFIG['BACKEND_API_URL']}/api/ring-events/{eid}",
                                        headers=get_api_headers()
                                    )
                                    if resp.status_code == 200:
                                        event_data = resp.json()
                                        if event_data.get("false_positive"):
                                            logger.info(f"🗑️ Skipping video for camera {cam} — ring event #{eid} marked as false positive")
                                            # Delete the downloaded recording
                                            if lp:
                                                Path(lp).unlink(missing_ok=True)
                                            fp_skipped += 1
                                            continue
                            except Exception as e:
                                logger.warning(f"Could not check false_positive status for event #{eid}: {e}")
                        
                        if url or lp:
                            await process_video_frames(cam, url, motion_time=mt, local_path=lp)
                            processed += 1
                    if fp_skipped:
                        logger.info(f"🎬 Skipped {fp_skipped} videos from false-positive events")
                    logger.info(f"🎬 Batch video processing complete: {processed}/{len(valid)} videos processed")
                    # Clear the queue
                    save_pending_videos([])
                # else: queue empty, nothing to do (silent — runs every minute)

        except Exception as e:
            logger.error(f"Error in video batch processor: {e}", exc_info=True)
            await asyncio.sleep(60)


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("Starting Deer Deterrent Coordinator")
    logger.info(f"Configuration: {json.dumps(CONFIG, indent=2)}")
    setup_mqtt()
    
    # Start background task to fetch settings from backend
    asyncio.create_task(settings_refresh_loop())
    
    # Start background task to process MQTT events
    asyncio.create_task(process_event_queue())
    
    # Start periodic snapshot polling if enabled
    if CONFIG["ENABLE_PERIODIC_SNAPSHOTS"]:
        asyncio.create_task(periodic_snapshot_poller())
        asyncio.create_task(cleanup_no_deer_snapshots())
        logger.info("Started periodic snapshot polling and cleanup tasks")
    
    # Start video batch processor (processes queued videos after active hours end)
    asyncio.create_task(video_batch_processor())
    pending_count = len(load_pending_videos())
    if pending_count > 0:
        logger.info(f"📹 {pending_count} videos pending from previous session")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    logger.info("Coordinator shut down")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "Deer Deterrent Coordinator",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check"""
    pending_videos = load_pending_videos()
    return {
        "status": "healthy",
        "mqtt_connected": mqtt_client and mqtt_client.is_connected() if mqtt_client else False,
        "last_activation": last_activation_time.isoformat() if last_activation_time else None,
        "active_hours": is_active_hours(),
        "pending_videos": len(pending_videos),
        "config": {
            "rainbird_configured": bool(CONFIG["RAINBIRD_IP"]),
            "irrigation_enabled": CONFIG["ENABLE_IRRIGATION"],
            "cooldown_seconds": CONFIG["COOLDOWN_SECONDS"],
            "confidence_threshold": CONFIG["CONFIDENCE_THRESHOLD"]
        }
    }


@app.post("/test-irrigation")
async def test_irrigation(request: Request):
    """Test irrigation by activating a specific zone."""
    try:
        payload = await request.json()
        zone = payload.get("zone", "1")
        duration = payload.get("duration", 60)  # seconds
        
        if not CONFIG["RAINBIRD_IP"]:
            return {"status": "error", "message": "Rainbird IP not configured in server .env"}
        
        success = await activate_rainbird(str(zone), int(duration))
        
        if success:
            return {"status": "success", "message": f"Zone {zone} activated for {max(1, round(int(duration)/60))} min"}
        else:
            return {"status": "error", "message": f"Failed to activate zone {zone}"}
    except Exception as e:
        logger.error(f"Test irrigation error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/stop-irrigation")
async def stop_irrigation_endpoint():
    """Stop all irrigation zones."""
    try:
        if not CONFIG["RAINBIRD_IP"]:
            return {"status": "error", "message": "Rainbird IP not configured in server .env"}
        
        success = await stop_rainbird()
        
        if success:
            return {"status": "success", "message": "All irrigation zones stopped"}
        else:
            return {"status": "error", "message": "Failed to stop irrigation"}
    except Exception as e:
        logger.error(f"Stop irrigation error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/webhook/test")
async def test_webhook(request: Request, background_tasks: BackgroundTasks):
    """Test endpoint for manual triggering"""
    try:
        payload = await request.json()
        
        camera_id = payload.get("camera_id", "test-camera")
        snapshot_url = payload.get("snapshot_url")
        timestamp = payload.get("timestamp", datetime.now().isoformat())
        
        if not snapshot_url:
            raise HTTPException(status_code=400, detail="Missing snapshot_url")
        
        background_tasks.add_task(process_camera_event, camera_id, timestamp, snapshot_url=snapshot_url)
        
        return {"status": "accepted", "message": "Processing test event"}
        
    except Exception as e:
        logger.error(f"Test webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats")
async def get_stats():
    """Get coordinator statistics"""
    snapshot_dir = Path("/app/snapshots")
    snapshot_count = len(list(snapshot_dir.glob("*.jpg"))) if snapshot_dir.exists() else 0
    
    cooldown_remaining = 0
    if last_activation_time:
        elapsed = (datetime.now() - last_activation_time).total_seconds()
        cooldown_remaining = max(0, CONFIG["COOLDOWN_SECONDS"] - elapsed)
    
    return {
        "total_snapshots": snapshot_count,
        "last_activation": last_activation_time.isoformat() if last_activation_time else None,
        "cooldown_remaining_seconds": int(cooldown_remaining),
        "active_hours": is_active_hours(),
        "mqtt_connected": mqtt_client.is_connected() if mqtt_client else False
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )
