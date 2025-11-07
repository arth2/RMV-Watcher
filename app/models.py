"""Database models for RMV-Watcher"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


class Settings(SQLModel, table=True):
    """Singleton settings table (id=1)"""
    id: int = Field(default=1, primary_key=True)
    appointment_link: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CheckRun(SQLModel, table=True):
    """Model for tracking check/scrape runs"""
    id: Optional[int] = Field(default=None, primary_key=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: str = Field(default="pending")  # pending, success, failed
    error_message: Optional[str] = None
    slots_found: int = Field(default=0)


class AppointmentSlot(SQLModel, table=True):
    """Model for storing appointment slot data"""
    id: Optional[int] = Field(default=None, primary_key=True)
    check_run_id: int = Field(foreign_key="checkrun.id", index=True)
    slot_time: datetime
    location: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AlertSent(SQLModel, table=True):
    """Model for tracking sent alerts (deduplication)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    fingerprint: str = Field(unique=True, index=True)
    check_run_id: int = Field(foreign_key="checkrun.id")
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    alert_type: str = Field(default="email")  # email, webhook, slack


# Legacy models (kept for compatibility)
class Link(SQLModel, table=True):
    """Model for tracking RMV links"""
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ScrapeResult(SQLModel, table=True):
    """Model for storing scrape results"""
    id: Optional[int] = Field(default=None, primary_key=True)
    link_id: int = Field(foreign_key="link.id")
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    status: str


class Notification(SQLModel, table=True):
    """Model for tracking notifications"""
    id: Optional[int] = Field(default=None, primary_key=True)
    scrape_result_id: int = Field(foreign_key="scraperesult.id")
    sent_at: datetime = Field(default_factory=datetime.utcnow)
    status: str
