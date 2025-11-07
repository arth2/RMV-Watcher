"""Tests for web scraper using static HTML fixtures"""

import pytest
import os
from datetime import datetime
from unittest.mock import patch, MagicMock
from playwright.sync_api import sync_playwright

from app.scraper import (
    _extract_date_from_group,
    _parse_date_string,
    _extract_times_from_group,
    _collect_time_slots,
)


class TestParseDateString:
    """Test date string parsing"""

    def test_parse_long_month_format(self):
        """Test parsing 'November 8, 2025' format"""
        result = _parse_date_string("November 8, 2025")
        assert result == "2025-11-08"

    def test_parse_short_month_format(self):
        """Test parsing 'Nov 8, 2025' format"""
        result = _parse_date_string("Nov 12, 2025")
        assert result == "2025-11-12"

    def test_parse_slash_format(self):
        """Test parsing '11/08/2025' format"""
        result = _parse_date_string("11/09/2025")
        assert result == "2025-11-09"

    def test_parse_iso_format(self):
        """Test parsing '2025-11-08' format"""
        result = _parse_date_string("2025-11-08")
        assert result == "2025-11-08"

    def test_parse_with_weekday_long(self):
        """Test parsing 'Friday, November 8, 2025' format"""
        result = _parse_date_string("Friday, November 8, 2025")
        assert result == "2025-11-08"

    def test_parse_with_weekday_short(self):
        """Test parsing 'Friday, Nov 8, 2025' format"""
        result = _parse_date_string("Friday, Nov 8, 2025")
        assert result == "2025-11-08"

    def test_parse_with_prefix(self):
        """Test parsing with 'Date:' prefix"""
        result = _parse_date_string("Date: November 8, 2025")
        assert result == "2025-11-08"

    def test_parse_invalid_date(self):
        """Test parsing invalid date returns None"""
        result = _parse_date_string("invalid date")
        assert result is None

    def test_parse_empty_string(self):
        """Test parsing empty string"""
        result = _parse_date_string("")
        assert result is None


class TestExtractDateFromGroup:
    """Test date extraction from HTML group elements"""

    @pytest.fixture
    def browser_context(self):
        """Set up Playwright browser context for testing"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            yield context
            browser.close()

    def test_extract_date_from_watertown_fixture(self, browser_context):
        """Test extracting dates from Watertown fixture"""
        page = browser_context.new_page()

        # Load the Watertown fixture
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'watertown_slots.html')
        page.goto(f'file://{os.path.abspath(fixture_path)}')

        # Get all date groups
        groups = page.locator('.DateTimeGrouping-Group').all()
        assert len(groups) > 0

        # Test first group
        date_str = _extract_date_from_group(groups[0])
        assert date_str == "2025-11-08"

    def test_extract_date_from_haymarket_fixture(self, browser_context):
        """Test extracting dates from Haymarket fixture"""
        page = browser_context.new_page()

        # Load the Haymarket fixture
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'haymarket_slots.html')
        page.goto(f'file://{os.path.abspath(fixture_path)}')

        # Get all date groups
        groups = page.locator('.DateTimeGrouping-Group').all()
        assert len(groups) > 0

        # Test first group (11/09/2025 format)
        date_str = _extract_date_from_group(groups[0])
        assert date_str == "2025-11-09"


class TestExtractTimesFromGroup:
    """Test time extraction from HTML group elements"""

    @pytest.fixture
    def browser_context(self):
        """Set up Playwright browser context for testing"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            yield context
            browser.close()

    def test_extract_times_from_watertown_fixture(self, browser_context):
        """Test extracting times from Watertown fixture"""
        page = browser_context.new_page()

        # Load the Watertown fixture
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'watertown_slots.html')
        page.goto(f'file://{os.path.abspath(fixture_path)}')

        # Get first date group
        groups = page.locator('.DateTimeGrouping-Group').all()
        times = _extract_times_from_group(groups[0])

        assert len(times) == 4
        assert "09:00 AM" in times
        assert "10:30 AM" in times
        assert "02:00 PM" in times
        assert "04:15 PM" in times

    def test_extract_times_from_haymarket_fixture(self, browser_context):
        """Test extracting times from Haymarket fixture"""
        page = browser_context.new_page()

        # Load the Haymarket fixture
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'haymarket_slots.html')
        page.goto(f'file://{os.path.abspath(fixture_path)}')

        # Get first date group
        groups = page.locator('.DateTimeGrouping-Group').all()
        times = _extract_times_from_group(groups[0])

        assert len(times) == 2
        assert "09:30 AM" in times
        assert "11:00 AM" in times


class TestCollectTimeSlots:
    """Test complete slot collection from fixtures"""

    @pytest.fixture
    def browser_context(self):
        """Set up Playwright browser context for testing"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            yield context
            browser.close()

    def test_collect_slots_from_watertown_fixture(self, browser_context):
        """Test collecting all slots from Watertown fixture"""
        page = browser_context.new_page()

        # Load the Watertown fixture
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'watertown_slots.html')
        page.goto(f'file://{os.path.abspath(fixture_path)}')

        # Collect all time slots
        slots_by_date = _collect_time_slots(page)

        # Should have 3 dates
        assert len(slots_by_date) == 3

        # Check November 8, 2025
        assert "2025-11-08" in slots_by_date
        assert len(slots_by_date["2025-11-08"]) == 4

        # Check November 10, 2025
        assert "2025-11-10" in slots_by_date
        assert len(slots_by_date["2025-11-10"]) == 3

        # Check November 15, 2025
        assert "2025-11-15" in slots_by_date
        assert len(slots_by_date["2025-11-15"]) == 2

    def test_collect_slots_from_haymarket_fixture(self, browser_context):
        """Test collecting all slots from Haymarket fixture"""
        page = browser_context.new_page()

        # Load the Haymarket fixture
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'haymarket_slots.html')
        page.goto(f'file://{os.path.abspath(fixture_path)}')

        # Collect all time slots
        slots_by_date = _collect_time_slots(page)

        # Should have 2 dates
        assert len(slots_by_date) == 2

        # Check November 9, 2025
        assert "2025-11-09" in slots_by_date
        assert len(slots_by_date["2025-11-09"]) == 2

        # Check November 12, 2025
        assert "2025-11-12" in slots_by_date
        assert len(slots_by_date["2025-11-12"]) == 3

    def test_slots_are_sorted(self, browser_context):
        """Test that collected slots are sorted"""
        page = browser_context.new_page()

        # Load the Watertown fixture
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'watertown_slots.html')
        page.goto(f'file://{os.path.abspath(fixture_path)}')

        # Collect all time slots
        slots_by_date = _collect_time_slots(page)

        # Check that times are sorted for each date
        for date_str, times in slots_by_date.items():
            assert times == sorted(times)

    def test_slots_no_duplicates(self, browser_context):
        """Test that duplicate times are removed"""
        page = browser_context.new_page()

        # Load the Watertown fixture
        fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'watertown_slots.html')
        page.goto(f'file://{os.path.abspath(fixture_path)}')

        # Collect all time slots
        slots_by_date = _collect_time_slots(page)

        # Check that there are no duplicates
        for date_str, times in slots_by_date.items():
            assert len(times) == len(set(times))


class TestScraperIntegration:
    """Integration tests for the complete scraper workflow"""

    def test_scraper_handles_missing_elements_gracefully(self):
        """Test that scraper handles missing elements without crashing"""
        # This would test error handling when elements are not found
        pass

    def test_scraper_handles_empty_page(self):
        """Test that scraper handles empty pages"""
        # This would test behavior with no appointment slots
        pass

    def test_scraper_handles_malformed_dates(self):
        """Test that scraper handles malformed date strings"""
        # This would test error recovery for invalid date formats
        pass

    def test_scraper_handles_malformed_times(self):
        """Test that scraper handles malformed time strings"""
        # This would test error recovery for invalid time formats
        pass
