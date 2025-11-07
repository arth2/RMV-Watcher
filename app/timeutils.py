"""Time and date utility functions"""

from datetime import datetime, timedelta, timezone
from typing import Optional


def get_current_utc_time() -> datetime:
    """Get current UTC time"""
    pass


def get_current_local_time() -> datetime:
    """Get current local time"""
    pass


def parse_datetime(date_string: str, format: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime]:
    """Parse a datetime string"""
    pass


def format_datetime(dt: datetime, format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a datetime object to string"""
    pass


def get_time_ago(dt: datetime) -> str:
    """Get human-readable time ago string"""
    pass


def is_within_time_range(dt: datetime, start: datetime, end: datetime) -> bool:
    """Check if datetime is within a time range"""
    pass


def add_days(dt: datetime, days: int) -> datetime:
    """Add days to a datetime"""
    pass


def subtract_days(dt: datetime, days: int) -> datetime:
    """Subtract days from a datetime"""
    pass


def get_start_of_day(dt: datetime) -> datetime:
    """Get start of day for a datetime"""
    pass


def get_end_of_day(dt: datetime) -> datetime:
    """Get end of day for a datetime"""
    pass


def convert_to_timezone(dt: datetime, tz: timezone) -> datetime:
    """Convert datetime to a specific timezone"""
    pass
