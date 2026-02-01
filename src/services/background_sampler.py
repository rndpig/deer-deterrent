"""
Background image sampling for training dataset diversity.
Captures random snapshots during active hours each week.
"""
import logging
from datetime import datetime, time as dt_time, timedelta
import random
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class BackgroundSampler:
    """
    Handles weekly random sampling of background images for training.
    Only samples during active hours to match production conditions.
    """
    
    def __init__(self, settings: Dict):
        """
        Initialize background sampler.
        
        Args:
            settings: System settings dictionary containing active_hours config
        """
        self.settings = settings
        self.samples_per_week = 1  # One sample per camera per week
        self.last_sample_date = {}  # Track last sample per camera
    
    def is_active_hours(self, check_time: datetime = None) -> bool:
        """
        Check if a given time is within active hours.
        
        Args:
            check_time: Time to check, defaults to now
            
        Returns:
            True if within active hours
        """
        if check_time is None:
            check_time = datetime.now()
        
        if not self.settings.get('active_hours_enabled', True):
            return True
        
        current_time = check_time.time()
        start_hour = self.settings.get('active_hours_start', 20)
        end_hour = self.settings.get('active_hours_end', 6)
        
        start_time = dt_time(start_hour, 0)
        end_time = dt_time(end_hour, 0)
        
        # Handle overnight period (e.g., 20:00 to 6:00)
        if start_time > end_time:
            return current_time >= start_time or current_time <= end_time
        else:
            return start_time <= current_time <= end_time
    
    def should_sample_now(self, camera_id: str) -> bool:
        """
        Determine if we should take a background sample now.
        
        Logic:
        - Only during active hours
        - Only once per week per camera
        - Random probability within active hours to distribute samples
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            True if should sample now
        """
        # Check if within active hours
        if not self.is_active_hours():
            return False
        
        # Check if we've already sampled this camera this week
        today = datetime.now().date()
        last_sample = self.last_sample_date.get(camera_id)
        
        if last_sample:
            days_since_sample = (today - last_sample).days
            if days_since_sample < 7:
                return False  # Already sampled this week
        
        # Random probability: 1% chance per check during active hours
        # Ensures we get one sample per week but it's randomly distributed
        # Assuming ~10 hours active, ~10 snapshots/hour = ~100 opportunities
        # 1% chance = expect 1 sample per week
        should_sample = random.random() < 0.01
        
        if should_sample:
            self.last_sample_date[camera_id] = today
            logger.info(f"Background sample scheduled for camera {camera_id}")
        
        return should_sample
    
    def get_random_active_hour(self) -> int:
        """
        Get a random hour within the active hours range.
        Useful for scheduling background samples.
        
        Returns:
            Random hour (0-23) within active hours
        """
        start_hour = self.settings.get('active_hours_start', 20)
        end_hour = self.settings.get('active_hours_end', 6)
        
        # Generate list of active hours
        if start_hour > end_hour:
            # Overnight period
            active_hours = list(range(start_hour, 24)) + list(range(0, end_hour + 1))
        else:
            # Normal period
            active_hours = list(range(start_hour, end_hour + 1))
        
        return random.choice(active_hours)
    
    def get_next_sample_time(self, camera_id: str) -> Optional[datetime]:
        """
        Calculate when the next background sample should occur for a camera.
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            Datetime of next scheduled sample, or None if already sampled this week
        """
        today = datetime.now().date()
        last_sample = self.last_sample_date.get(camera_id)
        
        if last_sample:
            days_since_sample = (today - last_sample).days
            if days_since_sample < 7:
                # Already sampled, next sample in (7 - days_since_sample) days
                days_until_next = 7 - days_since_sample
                next_date = today + timedelta(days=days_until_next)
                next_hour = self.get_random_active_hour()
                next_minute = random.randint(0, 59)
                return datetime.combine(next_date, dt_time(next_hour, next_minute))
        
        # No recent sample, schedule for random time in next 7 days during active hours
        days_offset = random.randint(0, 6)
        next_date = today + timedelta(days=days_offset)
        next_hour = self.get_random_active_hour()
        next_minute = random.randint(0, 59)
        
        return datetime.combine(next_date, dt_time(next_hour, next_minute))
    
    def reset_weekly_counters(self):
        """Reset the weekly sample tracking. Call this at start of each week."""
        self.last_sample_date.clear()
        logger.info("Reset weekly background sample counters")
