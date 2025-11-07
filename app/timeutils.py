"""Time and date utility functions"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple
import pytz

logger = logging.getLogger(__name__)

# Eastern Time timezone
ET = pytz.timezone('America/New_York')


def get_current_et_time() -> datetime:
    """Get current Eastern Time"""
    return datetime.now(ET)


def parse_appointment_datetime(date_str: str, time_str: str) -> datetime:
    """
    Parse appointment date and time strings into ET timezone-aware datetime.

    Args:
        date_str: Date string in YYYY-MM-DD format (e.g., "2025-11-08")
        time_str: Time string in 12-hour format (e.g., "09:00 AM", "02:30 PM")

    Returns:
        Timezone-aware datetime in Eastern Time
    """
    # Combine date and time strings
    datetime_str = f"{date_str} {time_str}"

    # Parse the datetime
    naive_dt = datetime.strptime(datetime_str, "%Y-%m-%d %I:%M %p")

    # Localize to Eastern Time
    et_dt = ET.localize(naive_dt)

    return et_dt


def filter_slots_by_14_days(
    scraped_slots: Dict[str, Dict[str, List[str]]]
) -> Tuple[Dict[str, Dict[str, List[datetime]]], List]:
    """
    Filter and convert scraped slots to only those within the next 14 days.

    Args:
        scraped_slots: Dict[location, Dict[date_str, List[time_str]]]
                      e.g., {"Watertown": {"2025-11-08": ["09:00 AM", "10:00 AM"], ...}, ...}

    Returns:
        Tuple of:
        - Filtered dict: Dict[location, Dict[date_str, List[datetime]]]
          with timezone-aware datetime objects
        - List of AppointmentSlot model instances ready for database
    """
    from app.models import AppointmentSlot

    now = get_current_et_time()
    cutoff = now + timedelta(days=14)

    filtered_dict = {}
    appointment_slots = []

    for location, dates in scraped_slots.items():
        location_slots = {}

        for date_str, time_strs in dates.items():
            date_slots = []

            for time_str in time_strs:
                try:
                    # Parse into ET datetime
                    slot_dt = parse_appointment_datetime(date_str, time_str)

                    # Filter: must be in the future and within 14 days
                    if now <= slot_dt <= cutoff:
                        date_slots.append(slot_dt)

                        # Create AppointmentSlot model (without check_run_id for now)
                        # check_run_id will be set by the caller
                        appointment_slots.append({
                            'slot_time': slot_dt,
                            'location': location,
                            'details': f"{date_str} {time_str}"
                        })

                except Exception as e:
                    logger.error(f"Error parsing slot {date_str} {time_str}: {e}")
                    continue

            # Only include dates that have valid slots after filtering
            if date_slots:
                location_slots[date_str] = date_slots

        # Only include locations that have valid slots after filtering
        if location_slots:
            filtered_dict[location] = location_slots

    return filtered_dict, appointment_slots


def convert_to_appointment_slots(
    filtered_dict: Dict[str, Dict[str, List[datetime]]],
    check_run_id: int
) -> List:
    """
    Convert filtered datetime dict to AppointmentSlot model instances.

    Args:
        filtered_dict: Dict[location, Dict[date_str, List[datetime]]]
        check_run_id: ID of the check run these slots belong to

    Returns:
        List of AppointmentSlot instances
    """
    from app.models import AppointmentSlot

    slots = []

    for location, dates in filtered_dict.items():
        for date_str, datetimes in dates.items():
            for dt in datetimes:
                slot = AppointmentSlot(
                    check_run_id=check_run_id,
                    slot_time=dt,
                    location=location,
                    details=f"{date_str} {dt.strftime('%I:%M %p')}"
                )
                slots.append(slot)

    return slots


# Legacy/utility functions

def get_current_utc_time() -> datetime:
    """Get current UTC time"""
    return datetime.now(timezone.utc)


def get_current_local_time() -> datetime:
    """Get current local time"""
    return datetime.now()


def parse_datetime(date_string: str, format: str = "%Y-%m-%d %H:%M:%S") -> Optional[datetime]:
    """Parse a datetime string"""
    try:
        return datetime.strptime(date_string, format)
    except ValueError as e:
        logger.error(f"Error parsing datetime '{date_string}': {e}")
        return None


def format_datetime(dt: datetime, format: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format a datetime object to string"""
    return dt.strftime(format)


def get_time_ago(dt: datetime) -> str:
    """Get human-readable time ago string"""
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    diff = now - dt

    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "just now"


def is_within_time_range(dt: datetime, start: datetime, end: datetime) -> bool:
    """Check if datetime is within a time range"""
    return start <= dt <= end


def add_days(dt: datetime, days: int) -> datetime:
    """Add days to a datetime"""
    return dt + timedelta(days=days)


def subtract_days(dt: datetime, days: int) -> datetime:
    """Subtract days from a datetime"""
    return dt - timedelta(days=days)


def get_start_of_day(dt: datetime) -> datetime:
    """Get start of day for a datetime"""
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def get_end_of_day(dt: datetime) -> datetime:
    """Get end of day for a datetime"""
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def convert_to_timezone(dt: datetime, tz: timezone) -> datetime:
    """Convert datetime to a specific timezone"""
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)
