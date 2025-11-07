"""Database models for RMV-Watcher"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


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


def create_link():
    """Create a new link"""
    pass


def create_scrape_result():
    """Create a new scrape result"""
    pass


def create_notification():
    """Create a new notification"""
    pass
