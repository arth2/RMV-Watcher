"""Tests for fingerprinting and deduplication logic"""

import pytest
import hashlib
from datetime import datetime
from unittest.mock import patch, MagicMock

from app.main import compute_fingerprint
from app import persistence
from app.models import AlertSent


class TestComputeFingerprint:
    """Test fingerprint computation for deduplication"""

    def test_fingerprint_basic(self):
        """Test basic fingerprint computation"""
        location = "Watertown"
        date = "2025-11-08"
        times = ["09:00 AM", "10:00 AM"]

        result = compute_fingerprint(location, date, times)

        # Should return a valid SHA256 hex digest
        assert isinstance(result, str)
        assert len(result) == 64  # SHA256 produces 64-character hex string
        assert all(c in '0123456789abcdef' for c in result)

    def test_fingerprint_deterministic(self):
        """Test that the same inputs produce the same fingerprint"""
        location = "Watertown"
        date = "2025-11-08"
        times = ["09:00 AM", "10:00 AM"]

        result1 = compute_fingerprint(location, date, times)
        result2 = compute_fingerprint(location, date, times)

        assert result1 == result2

    def test_fingerprint_order_independent(self):
        """Test that time order doesn't affect fingerprint (times are sorted)"""
        location = "Watertown"
        date = "2025-11-08"
        times1 = ["09:00 AM", "10:00 AM", "02:00 PM"]
        times2 = ["02:00 PM", "09:00 AM", "10:00 AM"]

        result1 = compute_fingerprint(location, date, times1)
        result2 = compute_fingerprint(location, date, times2)

        # Should be the same because times are sorted internally
        assert result1 == result2

    def test_fingerprint_different_times_different_hash(self):
        """Test that different times produce different fingerprints"""
        location = "Watertown"
        date = "2025-11-08"
        times1 = ["09:00 AM", "10:00 AM"]
        times2 = ["09:00 AM", "11:00 AM"]

        result1 = compute_fingerprint(location, date, times1)
        result2 = compute_fingerprint(location, date, times2)

        assert result1 != result2

    def test_fingerprint_different_location_different_hash(self):
        """Test that different locations produce different fingerprints"""
        date = "2025-11-08"
        times = ["09:00 AM", "10:00 AM"]

        result1 = compute_fingerprint("Watertown", date, times)
        result2 = compute_fingerprint("Haymarket", date, times)

        assert result1 != result2

    def test_fingerprint_different_date_different_hash(self):
        """Test that different dates produce different fingerprints"""
        location = "Watertown"
        times = ["09:00 AM", "10:00 AM"]

        result1 = compute_fingerprint(location, "2025-11-08", times)
        result2 = compute_fingerprint(location, "2025-11-09", times)

        assert result1 != result2

    def test_fingerprint_single_time(self):
        """Test fingerprint with a single time"""
        location = "Watertown"
        date = "2025-11-08"
        times = ["09:00 AM"]

        result = compute_fingerprint(location, date, times)

        assert len(result) == 64

    def test_fingerprint_many_times(self):
        """Test fingerprint with many time slots"""
        location = "Watertown"
        date = "2025-11-08"
        times = [f"{h:02d}:00 AM" for h in range(8, 12)]

        result = compute_fingerprint(location, date, times)

        assert len(result) == 64

    def test_fingerprint_matches_expected_algorithm(self):
        """Test that fingerprint matches expected SHA256(location|date|sorted_times)"""
        location = "Watertown"
        date = "2025-11-08"
        times = ["10:00 AM", "09:00 AM"]  # Unsorted

        # Compute expected fingerprint manually
        sorted_times = sorted(times)
        fingerprint_str = f"{location}|{date}|{sorted_times}"
        expected = hashlib.sha256(fingerprint_str.encode()).hexdigest()

        result = compute_fingerprint(location, date, times)

        assert result == expected


class TestFingerprintDeduplication:
    """Test deduplication logic using fingerprints"""

    def test_has_fingerprint_returns_false_for_new(self):
        """Test that has_fingerprint returns False for a new fingerprint"""
        # This test would require database setup
        # For now, we'll test the logic structure
        pass

    def test_has_fingerprint_returns_true_for_existing(self):
        """Test that has_fingerprint returns True for existing fingerprint"""
        # This test would require database setup
        pass

    @patch('app.persistence.get_session')
    def test_has_fingerprint_queries_database(self, mock_get_session):
        """Test that has_fingerprint queries the database correctly"""
        # Mock the session
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        # Mock the query result
        mock_session.exec.return_value.first.return_value = None

        fingerprint = "abc123"
        result = persistence.has_fingerprint(fingerprint)

        # Should query the database
        assert mock_session.exec.called
        assert result is False

    @patch('app.persistence.get_session')
    def test_has_fingerprint_returns_true_when_found(self, mock_get_session):
        """Test that has_fingerprint returns True when fingerprint exists"""
        # Mock the session
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        # Mock finding a fingerprint
        mock_alert = AlertSent(
            id=1,
            fingerprint="abc123",
            check_run_id=1,
            alert_type="email"
        )
        mock_session.exec.return_value.first.return_value = mock_alert

        fingerprint = "abc123"
        result = persistence.has_fingerprint(fingerprint)

        assert result is True

    def test_deduplication_scenario_same_slots_twice(self):
        """Integration test: same slots should not trigger duplicate alerts"""
        location = "Watertown"
        date = "2025-11-08"
        times = ["09:00 AM", "10:00 AM"]

        # First run - new slots
        fp1 = compute_fingerprint(location, date, times)

        # Second run - same slots (should produce same fingerprint)
        fp2 = compute_fingerprint(location, date, times)

        assert fp1 == fp2
        # In practice, fp2 would be skipped because has_fingerprint(fp2) would return True

    def test_deduplication_scenario_additional_slot(self):
        """Integration test: additional slot should trigger new alert"""
        location = "Watertown"
        date = "2025-11-08"

        # First run - two slots
        times1 = ["09:00 AM", "10:00 AM"]
        fp1 = compute_fingerprint(location, date, times1)

        # Second run - three slots (one added)
        times2 = ["09:00 AM", "10:00 AM", "02:00 PM"]
        fp2 = compute_fingerprint(location, date, times2)

        # Should be different fingerprints
        assert fp1 != fp2
        # In practice, fp2 would trigger a new alert

    def test_deduplication_scenario_removed_slot(self):
        """Integration test: removed slot should trigger new alert"""
        location = "Watertown"
        date = "2025-11-08"

        # First run - three slots
        times1 = ["09:00 AM", "10:00 AM", "02:00 PM"]
        fp1 = compute_fingerprint(location, date, times1)

        # Second run - two slots (one removed)
        times2 = ["09:00 AM", "10:00 AM"]
        fp2 = compute_fingerprint(location, date, times2)

        # Should be different fingerprints
        assert fp1 != fp2

    def test_deduplication_different_locations_independent(self):
        """Test that same times at different locations are tracked independently"""
        date = "2025-11-08"
        times = ["09:00 AM", "10:00 AM"]

        fp_watertown = compute_fingerprint("Watertown", date, times)
        fp_haymarket = compute_fingerprint("Haymarket", date, times)

        # Should be different fingerprints
        assert fp_watertown != fp_haymarket

    def test_deduplication_different_dates_independent(self):
        """Test that same times on different dates are tracked independently"""
        location = "Watertown"
        times = ["09:00 AM", "10:00 AM"]

        fp_date1 = compute_fingerprint(location, "2025-11-08", times)
        fp_date2 = compute_fingerprint(location, "2025-11-09", times)

        # Should be different fingerprints
        assert fp_date1 != fp_date2


class TestFingerprintPersistence:
    """Test fingerprint storage and retrieval"""

    @patch('app.persistence.get_session')
    def test_record_alert_fingerprint(self, mock_get_session):
        """Test recording a fingerprint after sending alert"""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        fingerprint = "abc123"
        check_run_id = 1

        persistence.record_alert_fingerprint(
            fingerprint=fingerprint,
            check_run_id=check_run_id,
            alert_type="email"
        )

        # Should add the alert to the session
        assert mock_session.add.called
        # Should commit
        assert mock_session.commit.called

    def test_fingerprint_uniqueness(self):
        """Test that fingerprints enforce uniqueness (schema level)"""
        # This is enforced by the unique constraint on AlertSent.fingerprint
        # Testing would require actual database setup
        pass
