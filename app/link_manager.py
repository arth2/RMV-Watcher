"""Link management functionality"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import pytz

from app.models import Link, Settings
from app import persistence

logger = logging.getLogger(__name__)

# Eastern Time timezone
ET = pytz.timezone('America/New_York')


# ============================================================================
# Settings Management Commands
# ============================================================================

def set_link(link: str, expires: str) -> Settings:
    """
    Set appointment link and expiration time in Settings.

    Args:
        link: Appointment booking URL
        expires: Expiration datetime in ISO8601 format (ET timezone)
                 e.g., "2025-11-15T23:59:59" or "2025-11-15 23:59:59"

    Returns:
        Updated Settings object

    Example:
        set_link("https://example.com/appt", "2025-11-15T23:59:59")
    """
    logger.info(f"Setting appointment link: {link}")
    logger.info(f"Setting expiration: {expires}")

    # Parse expiration datetime (assume ET timezone)
    try:
        # Try ISO8601 format with T separator
        if 'T' in expires:
            naive_dt = datetime.fromisoformat(expires.replace('Z', ''))
        else:
            # Try space-separated format
            naive_dt = datetime.strptime(expires, "%Y-%m-%d %H:%M:%S")

        # Localize to Eastern Time
        expires_dt = ET.localize(naive_dt)
        logger.info(f"Parsed expiration as ET: {expires_dt}")

    except ValueError as e:
        logger.error(f"Failed to parse expiration datetime: {e}")
        raise ValueError(f"Invalid datetime format. Use ISO8601 format like '2025-11-15T23:59:59' or '2025-11-15 23:59:59'. Error: {e}")

    # Get or create Settings (id=1)
    with persistence.get_session() as session:
        settings = session.get(Settings, 1)

        if settings is None:
            # Create new settings record
            settings = Settings(
                id=1,
                appointment_link=link,
                expires_at=expires_dt,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(settings)
            logger.info("Created new Settings record")
        else:
            # Update existing settings
            settings.appointment_link = link
            settings.expires_at = expires_dt
            settings.updated_at = datetime.utcnow()
            logger.info("Updated existing Settings record")

        session.commit()
        session.refresh(settings)

        logger.info(f"Settings saved successfully: link={link}, expires={expires_dt}")
        return settings


def show_settings() -> Optional[Settings]:
    """
    Display current Settings (appointment link and expiration).

    Returns:
        Settings object or None if not configured
    """
    with persistence.get_session() as session:
        settings = session.get(Settings, 1)

        if settings is None:
            print("No settings configured.")
            print("Use set_link() to configure appointment link and expiration.")
            return None

        print("=" * 60)
        print("RMV Watcher Settings")
        print("=" * 60)
        print(f"Appointment Link: {settings.appointment_link or 'Not set'}")

        if settings.expires_at:
            # Convert to ET for display
            if settings.expires_at.tzinfo is None:
                # Naive datetime - assume UTC
                expires_et = pytz.utc.localize(settings.expires_at).astimezone(ET)
            else:
                expires_et = settings.expires_at.astimezone(ET)

            print(f"Expires At (ET):  {expires_et.strftime('%Y-%m-%d %H:%M:%S %Z')}")

            # Calculate time remaining
            now = datetime.now(ET)
            if expires_et > now:
                time_left = expires_et - now
                days = time_left.days
                hours = time_left.seconds // 3600
                minutes = (time_left.seconds % 3600) // 60
                print(f"Time Remaining:   {days} days, {hours} hours, {minutes} minutes")
            else:
                print("Status:           EXPIRED")
        else:
            print("Expires At:       Not set")

        print(f"\nCreated At:       {settings.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Updated At:       {settings.updated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 60)

        return settings


# ============================================================================
# Legacy Link Management Functions
# ============================================================================

def add_link(url: str) -> Link:
    """Add a new link to watch"""
    pass


def remove_link(link_id: int) -> bool:
    """Remove a link from watching"""
    pass


def get_active_links() -> List[Link]:
    """Get all active links to be scraped"""
    pass


def validate_link(url: str) -> bool:
    """Validate a link URL"""
    pass


def parse_link_url(url: str) -> Dict[str, Any]:
    """Parse and extract information from a link URL"""
    pass


def is_duplicate_link(url: str) -> bool:
    """Check if a link is already being tracked"""
    pass


def update_link_status(link_id: int, status: str):
    """Update the status of a link"""
    pass


def get_link_info(link_id: int) -> Optional[Dict[str, Any]]:
    """Get detailed information about a link"""
    pass


def import_links_from_file(filepath: str) -> int:
    """Import links from a file"""
    pass


def export_links_to_file(filepath: str) -> int:
    """Export links to a file"""
    pass
