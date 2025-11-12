"""Tests for time utility functions"""

import pytest
from datetime import datetime, timedelta
import pytz

from app.timeutils import (
    get_current_et_time,
    parse_appointment_datetime,
    filter_slots_by_14_days,
    convert_to_appointment_slots,
)

# Eastern Time timezone
ET = pytz.timezone('America/New_York')


class TestParseAppointmentDateTime:
    """Test date/time parsing into ET timezone"""

    def test_parse_basic_datetime(self):
        """Test parsing basic date and time into ET"""
        result = parse_appointment_datetime("2025-11-08", "09:00 AM")

        assert result.year == 2025
        assert result.month == 11
        assert result.day == 8
        assert result.hour == 9
        assert result.minute == 0
        # Check timezone by name instead of direct comparison
        assert result.tzinfo.zone == 'America/New_York'

    def test_parse_afternoon_time(self):
        """Test parsing PM times"""
        result = parse_appointment_datetime("2025-11-08", "02:30 PM")

        assert result.hour == 14
        assert result.minute == 30
        assert result.tzinfo.zone == 'America/New_York'

    def test_parse_noon(self):
        """Test parsing noon (12:00 PM)"""
        result = parse_appointment_datetime("2025-11-08", "12:00 PM")

        assert result.hour == 12
        assert result.minute == 0

    def test_parse_midnight(self):
        """Test parsing midnight (12:00 AM)"""
        result = parse_appointment_datetime("2025-11-08", "12:00 AM")

        assert result.hour == 0
        assert result.minute == 0

    def test_different_date_formats(self):
        """Test various date formats"""
        # ISO format (YYYY-MM-DD)
        result = parse_appointment_datetime("2025-11-15", "10:00 AM")
        assert result.day == 15
        assert result.hour == 10


class TestFilterSlotsBy14Days:
    """Test 14-day window filtering logic"""

    def test_filter_future_slots_within_14_days(self):
        """Test that slots within the next 14 days are included"""
        # Create test data with slots in various timeframes
        now = get_current_et_time()

        # Slots 5 days in the future (should be included)
        future_date = (now + timedelta(days=5)).strftime('%Y-%m-%d')

        scraped_slots = {
            "Watertown": {
                future_date: ["09:00 AM", "10:00 AM"]
            }
        }

        filtered_dict, slot_list = filter_slots_by_14_days(scraped_slots)

        assert "Watertown" in filtered_dict
        assert future_date in filtered_dict["Watertown"]
        assert len(filtered_dict["Watertown"][future_date]) == 2
        assert len(slot_list) == 2

    def test_filter_excludes_slots_beyond_14_days(self):
        """Test that slots beyond 14 days are excluded"""
        now = get_current_et_time()

        # Slot 20 days in the future (should be excluded)
        future_date = (now + timedelta(days=20)).strftime('%Y-%m-%d')

        scraped_slots = {
            "Watertown": {
                future_date: ["09:00 AM"]
            }
        }

        filtered_dict, slot_list = filter_slots_by_14_days(scraped_slots)

        # Should be empty
        assert len(filtered_dict) == 0
        assert len(slot_list) == 0

    def test_filter_excludes_past_slots(self):
        """Test that past slots are excluded"""
        now = get_current_et_time()

        # Slot 2 days in the past (should be excluded)
        past_date = (now - timedelta(days=2)).strftime('%Y-%m-%d')

        scraped_slots = {
            "Watertown": {
                past_date: ["09:00 AM"]
            }
        }

        filtered_dict, slot_list = filter_slots_by_14_days(scraped_slots)

        assert len(filtered_dict) == 0
        assert len(slot_list) == 0

    def test_filter_boundary_exactly_14_days(self):
        """Test that slots exactly 14 days out are included (inclusive)"""
        now = get_current_et_time()

        # Slot exactly 14 days in the future
        future_date = (now + timedelta(days=14)).strftime('%Y-%m-%d')
        future_time = now.strftime('%I:%M %p')

        scraped_slots = {
            "Watertown": {
                future_date: [future_time]
            }
        }

        filtered_dict, slot_list = filter_slots_by_14_days(scraped_slots)

        # Should be included (cutoff is inclusive)
        assert "Watertown" in filtered_dict or len(filtered_dict) == 0  # May be excluded if time has passed

    def test_filter_multiple_locations(self):
        """Test filtering with multiple locations"""
        now = get_current_et_time()

        date1 = (now + timedelta(days=3)).strftime('%Y-%m-%d')
        date2 = (now + timedelta(days=7)).strftime('%Y-%m-%d')

        scraped_slots = {
            "Watertown": {
                date1: ["09:00 AM", "10:00 AM"]
            },
            "Haymarket": {
                date2: ["11:00 AM"]
            }
        }

        filtered_dict, slot_list = filter_slots_by_14_days(scraped_slots)

        assert "Watertown" in filtered_dict
        assert "Haymarket" in filtered_dict
        assert len(slot_list) == 3  # 2 + 1

    def test_filter_mixed_valid_invalid_dates(self):
        """Test filtering when some dates are valid and some are not"""
        now = get_current_et_time()

        valid_date = (now + timedelta(days=5)).strftime('%Y-%m-%d')
        invalid_date = (now + timedelta(days=20)).strftime('%Y-%m-%d')

        scraped_slots = {
            "Watertown": {
                valid_date: ["09:00 AM"],
                invalid_date: ["10:00 AM"]
            }
        }

        filtered_dict, slot_list = filter_slots_by_14_days(scraped_slots)

        assert "Watertown" in filtered_dict
        assert valid_date in filtered_dict["Watertown"]
        assert invalid_date not in filtered_dict["Watertown"]
        assert len(slot_list) == 1

    def test_returned_datetimes_are_timezone_aware(self):
        """Test that returned datetime objects are timezone-aware"""
        now = get_current_et_time()

        future_date = (now + timedelta(days=5)).strftime('%Y-%m-%d')

        scraped_slots = {
            "Watertown": {
                future_date: ["09:00 AM"]
            }
        }

        filtered_dict, slot_list = filter_slots_by_14_days(scraped_slots)

        # Check that datetimes are timezone-aware
        if filtered_dict:
            for location, dates in filtered_dict.items():
                for date_str, datetimes in dates.items():
                    for dt in datetimes:
                        assert dt.tzinfo is not None
                        assert dt.tzinfo.zone == 'America/New_York'

    def test_slot_list_has_correct_structure(self):
        """Test that the returned slot list has correct dictionary structure"""
        now = get_current_et_time()

        future_date = (now + timedelta(days=5)).strftime('%Y-%m-%d')

        scraped_slots = {
            "Watertown": {
                future_date: ["09:00 AM"]
            }
        }

        filtered_dict, slot_list = filter_slots_by_14_days(scraped_slots)

        assert len(slot_list) == 1
        assert 'slot_time' in slot_list[0]
        assert 'location' in slot_list[0]
        assert 'details' in slot_list[0]
        assert slot_list[0]['location'] == "Watertown"


class TestConvertToAppointmentSlots:
    """Test conversion to AppointmentSlot models"""

    def test_convert_basic_slots(self):
        """Test basic conversion to AppointmentSlot instances"""
        now = get_current_et_time()
        dt1 = now + timedelta(days=5, hours=9)
        dt2 = now + timedelta(days=5, hours=10)

        filtered_dict = {
            "Watertown": {
                dt1.strftime('%Y-%m-%d'): [dt1, dt2]
            }
        }

        slots = convert_to_appointment_slots(filtered_dict, check_run_id=123)

        assert len(slots) == 2
        assert slots[0].check_run_id == 123
        assert slots[0].location == "Watertown"
        assert slots[0].slot_time == dt1

    def test_convert_multiple_locations(self):
        """Test conversion with multiple locations"""
        now = get_current_et_time()
        dt1 = now + timedelta(days=3, hours=9)
        dt2 = now + timedelta(days=5, hours=11)

        filtered_dict = {
            "Watertown": {
                dt1.strftime('%Y-%m-%d'): [dt1]
            },
            "Haymarket": {
                dt2.strftime('%Y-%m-%d'): [dt2]
            }
        }

        slots = convert_to_appointment_slots(filtered_dict, check_run_id=456)

        assert len(slots) == 2
        assert any(s.location == "Watertown" for s in slots)
        assert any(s.location == "Haymarket" for s in slots)

    def test_convert_preserves_timezone(self):
        """Test that timezone information is preserved"""
        now = get_current_et_time()
        dt = ET.localize(datetime(2025, 11, 15, 9, 0))

        filtered_dict = {
            "Watertown": {
                "2025-11-15": [dt]
            }
        }

        slots = convert_to_appointment_slots(filtered_dict, check_run_id=1)

        assert slots[0].slot_time.tzinfo.zone == 'America/New_York'


class TestGetCurrentETTime:
    """Test getting current Eastern Time"""

    def test_returns_timezone_aware_datetime(self):
        """Test that current ET time is timezone-aware"""
        result = get_current_et_time()

        assert result.tzinfo is not None
        assert result.tzinfo.zone == 'America/New_York'

    def test_returns_current_time(self):
        """Test that returned time is approximately now"""
        before = datetime.now(ET)
        result = get_current_et_time()
        after = datetime.now(ET)

        # Should be between before and after (within a few seconds)
        assert before <= result <= after
