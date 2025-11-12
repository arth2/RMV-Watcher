"""Database persistence layer for RMV-Watcher"""

import os
import logging
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, create_engine, Session, select

from app.models import (
    Settings, CheckRun, AppointmentSlot, AlertSent,
    Link, ScrapeResult, Notification
)

logger = logging.getLogger(__name__)

# Database configuration
DB_PATH = "/tmp/state.sqlite3"
DATABASE_URL = f"sqlite:///{DB_PATH}"

# GCS configuration
USE_GCS_STORAGE = os.getenv('USE_GCS_STORAGE', 'false').lower() == 'true'
GCS_BUCKET = os.getenv('GCS_BUCKET_NAME', '')

# Global engine instance
_engine = None
_gcs_client = None


def _get_gcs_client():
    """Lazy load GCS client"""
    global _gcs_client
    if _gcs_client is None and USE_GCS_STORAGE:
        try:
            from google.cloud import storage
            _gcs_client = storage.Client()
        except Exception as e:
            logger.error(f"Failed to initialize GCS client: {e}")
    return _gcs_client


def download_from_gcs():
    """Download state.sqlite3 from GCS if it exists"""
    if not USE_GCS_STORAGE or not GCS_BUCKET:
        return

    try:
        client = _get_gcs_client()
        if not client:
            return

        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob('state.sqlite3')

        if blob.exists():
            logger.info(f"Downloading state.sqlite3 from GCS bucket: {GCS_BUCKET}")
            blob.download_to_filename(DB_PATH)
            logger.info("Database downloaded successfully from GCS")
        else:
            logger.info("No existing database found in GCS")
    except Exception as e:
        logger.error(f"Failed to download from GCS: {e}")


def upload_to_gcs():
    """Upload state.sqlite3 to GCS"""
    if not USE_GCS_STORAGE or not GCS_BUCKET:
        return

    if not os.path.exists(DB_PATH):
        logger.warning("Database file does not exist, skipping upload")
        return

    try:
        client = _get_gcs_client()
        if not client:
            return

        bucket = client.bucket(GCS_BUCKET)
        blob = bucket.blob('state.sqlite3')

        logger.info(f"Uploading state.sqlite3 to GCS bucket: {GCS_BUCKET}")
        blob.upload_from_filename(DB_PATH)
        logger.info("Database uploaded successfully to GCS")
    except Exception as e:
        logger.error(f"Failed to upload to GCS: {e}")


def get_db():
    """Get database engine, initializing if necessary"""
    global _engine

    if _engine is None:
        # Download from GCS on first initialization
        download_from_gcs()

        # Create engine
        _engine = create_engine(DATABASE_URL, echo=False)

        # Create all tables
        SQLModel.metadata.create_all(_engine)
        logger.info(f"Database initialized at {DB_PATH}")

    return _engine


@contextmanager
def get_session():
    """Get a database session with automatic commit and GCS upload"""
    engine = get_db()
    session = Session(engine)
    try:
        yield session
        session.commit()
        # Upload to GCS after successful commit
        upload_to_gcs()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()


def init_database():
    """Initialize database tables"""
    engine = get_db()
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables initialized")


# ============================================================================
# Helper Functions
# ============================================================================

def save_check_run(check_run: CheckRun) -> int:
    """Save a check run to database and return its ID"""
    with get_session() as session:
        session.add(check_run)
        session.commit()
        session.refresh(check_run)
        # Get the ID while session is still open
        check_run_id = check_run.id

    # Return just the ID - simple integer, no session binding issues
    return check_run_id


def save_slots(slots: List[AppointmentSlot]) -> int:
    """Save appointment slots to database"""
    if not slots:
        return 0

    with get_session() as session:
        for slot in slots:
            session.add(slot)
        session.commit()
        return len(slots)


def record_alert_fingerprint(fingerprint: str, check_run_id: int, alert_type: str = "email") -> AlertSent:
    """Record an alert fingerprint to prevent duplicate alerts"""
    with get_session() as session:
        alert = AlertSent(
            fingerprint=fingerprint,
            check_run_id=check_run_id,
            alert_type=alert_type
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)

        # Load all attributes before session closes
        _ = alert.id
        _ = alert.fingerprint
        _ = alert.check_run_id
        _ = alert.sent_at
        _ = alert.alert_type

        # Expunge to make detached but keep data
        session.expunge(alert)

    return alert


def has_fingerprint(fingerprint: str) -> bool:
    """Check if an alert fingerprint already exists"""
    with get_session() as session:
        statement = select(AlertSent).where(AlertSent.fingerprint == fingerprint)
        result = session.exec(statement).first()
        return result is not None


# ============================================================================
# Legacy Functions (kept for compatibility)
# ============================================================================

def save_link(link: Link):
    """Save a link to database"""
    with get_session() as session:
        session.add(link)


def get_link(link_id: int) -> Optional[Link]:
    """Get a link by ID"""
    with get_session() as session:
        link = session.get(Link, link_id)
        if link:
            # Load all attributes and expunge
            _ = (link.id, link.url, link.expires_at, link.created_at, link.updated_at)
            session.expunge(link)
        return link


def get_all_links():
    """Get all links from database"""
    with get_session() as session:
        statement = select(Link)
        links = list(session.exec(statement).all())
        # Expunge all links to make them detached
        for link in links:
            _ = (link.id, link.url, link.expires_at, link.created_at, link.updated_at)
            session.expunge(link)
        return links


def update_link(link: Link):
    """Update a link in database"""
    with get_session() as session:
        session.add(link)


def delete_link(link_id: int):
    """Delete a link from database"""
    with get_session() as session:
        link = session.get(Link, link_id)
        if link:
            session.delete(link)


def save_scrape_result(result: ScrapeResult):
    """Save a scrape result to database"""
    with get_session() as session:
        session.add(result)


def get_scrape_result(result_id: int) -> Optional[ScrapeResult]:
    """Get a scrape result by ID"""
    with get_session() as session:
        result = session.get(ScrapeResult, result_id)
        if result:
            # Load all attributes and expunge
            _ = (result.id, result.link_id, result.scraped_at, result.slots_found, result.status)
            session.expunge(result)
        return result


def get_scrape_results_by_link(link_id: int):
    """Get all scrape results for a link"""
    with get_session() as session:
        statement = select(ScrapeResult).where(ScrapeResult.link_id == link_id)
        results = list(session.exec(statement).all())
        # Expunge all results to make them detached
        for result in results:
            _ = (result.id, result.link_id, result.scraped_at, result.slots_found, result.status)
            session.expunge(result)
        return results


def save_notification(notification: Notification):
    """Save a notification to database"""
    with get_session() as session:
        session.add(notification)


def get_notification(notification_id: int) -> Optional[Notification]:
    """Get a notification by ID"""
    with get_session() as session:
        notification = session.get(Notification, notification_id)
        if notification:
            # Load all attributes and expunge
            _ = (notification.id, notification.scrape_result_id, notification.sent_at, notification.notification_type)
            session.expunge(notification)
        return notification


def get_notifications_by_scrape_result(scrape_result_id: int):
    """Get all notifications for a scrape result"""
    with get_session() as session:
        statement = select(Notification).where(
            Notification.scrape_result_id == scrape_result_id
        )
        notifications = list(session.exec(statement).all())
        # Expunge all notifications to make them detached
        for notification in notifications:
            _ = (notification.id, notification.scrape_result_id, notification.sent_at, notification.notification_type)
            session.expunge(notification)
        return notifications
