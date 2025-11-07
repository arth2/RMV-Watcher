"""Web scraping functionality using Playwright"""

import os
import logging
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from typing import Optional, Dict, Any, List

from app.selectors import get_selectors

logger = logging.getLogger(__name__)

# Configuration
HEADLESS_MODE = os.getenv('HEADLESS_MODE', 'True') == 'True'
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))

# Target locations to scrape
TARGET_LOCATIONS = ['Watertown', 'Haymarket', 'Wilmington']


def scrape_appointment_slots(appointment_link: str) -> Dict[str, Dict[str, List[str]]]:
    """
    Scrape appointment slots from the RMV appointment link.

    Args:
        appointment_link: URL to the appointment booking page

    Returns:
        Dict[location, Dict[date_str, List[time_str]]]
        e.g., {"Watertown": {"2025-11-08": ["09:00 AM", "10:00 AM"], ...}, ...}
    """
    logger.info(f"Starting scrape of appointment link: {appointment_link}")

    results = {}

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=HEADLESS_MODE)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()

        try:
            # Navigate to appointment link
            logger.info(f"Navigating to: {appointment_link}")
            page.goto(appointment_link, wait_until='networkidle', timeout=30000)

            # Wait for page to load
            page.wait_for_load_state('domcontentloaded')
            time.sleep(2)  # Give page time to fully render

            # Scrape each target location
            for location in TARGET_LOCATIONS:
                logger.info(f"Attempting to scrape location: {location}")
                try:
                    location_slots = _scrape_location(page, location, appointment_link)
                    if location_slots:
                        results[location] = location_slots
                        logger.info(f"Found {sum(len(times) for times in location_slots.values())} slots for {location}")
                    else:
                        logger.warning(f"No slots found for {location}")
                except Exception as e:
                    logger.error(f"Error scraping {location}: {e}", exc_info=True)
                    continue

        except Exception as e:
            logger.error(f"Error during scraping: {e}", exc_info=True)
            raise
        finally:
            browser.close()

    logger.info(f"Scraping complete. Found slots in {len(results)} location(s)")
    return results


def _scrape_location(page: Page, location: str, base_url: str) -> Dict[str, List[str]]:
    """
    Scrape appointment slots for a specific location.

    Args:
        page: Playwright page object
        location: Location name (exact match)
        base_url: Base URL to navigate back to if needed

    Returns:
        Dict[date_str, List[time_str]]
    """
    # Navigate back to main page if needed
    if page.url != base_url:
        page.goto(base_url, wait_until='networkidle', timeout=30000)
        time.sleep(2)

    # Find and click the location button/link
    try:
        # Try different selector strategies
        location_clicked = False

        # Strategy 1: Look for exact text in buttons
        try:
            location_button = page.get_by_role('button', name=location, exact=True)
            if location_button.is_visible(timeout=5000):
                location_button.click()
                location_clicked = True
                logger.info(f"Clicked location button: {location}")
        except:
            pass

        # Strategy 2: Look for links with exact text
        if not location_clicked:
            try:
                location_link = page.get_by_role('link', name=location, exact=True)
                if location_link.is_visible(timeout=5000):
                    location_link.click()
                    location_clicked = True
                    logger.info(f"Clicked location link: {location}")
            except:
                pass

        # Strategy 3: Look for any element containing exact text
        if not location_clicked:
            try:
                location_element = page.locator(f'text="{location}"').first
                if location_element.is_visible(timeout=5000):
                    location_element.click()
                    location_clicked = True
                    logger.info(f"Clicked location element: {location}")
            except:
                pass

        if not location_clicked:
            logger.warning(f"Could not find clickable element for location: {location}")
            return {}

        # Wait for navigation/content to load
        time.sleep(2)
        page.wait_for_load_state('domcontentloaded')

    except Exception as e:
        logger.error(f"Error clicking location {location}: {e}")
        return {}

    # Expand all DateTimeGrouping-Group accordions and collect times
    slots_by_date = _collect_time_slots(page)

    return slots_by_date


def _collect_time_slots(page: Page) -> Dict[str, List[str]]:
    """
    Expand all DateTimeGrouping-Group elements and collect time slots.

    Returns:
        Dict[date_str, List[time_str]]
    """
    slots_by_date = {}

    try:
        # Find all DateTimeGrouping-Group elements
        date_groups = page.locator('.DateTimeGrouping-Group').all()
        logger.info(f"Found {len(date_groups)} date groups")

        for i, group in enumerate(date_groups):
            try:
                # Scroll into view
                group.scroll_into_view_if_needed()
                time.sleep(0.5)

                # Try to expand the group (if it's an accordion)
                # Look for radio button or clickable header
                try:
                    # Try clicking the group header/radio
                    radio = group.locator('input[type="radio"]').first
                    if radio.is_visible():
                        radio.check()
                        time.sleep(0.5)
                        logger.debug(f"Expanded date group {i}")
                except:
                    # Try clicking the group itself
                    try:
                        group.click()
                        time.sleep(0.5)
                    except:
                        pass

                # Extract date
                date_str = _extract_date_from_group(group)
                if not date_str:
                    logger.warning(f"Could not extract date from group {i}")
                    continue

                # Extract times
                times = _extract_times_from_group(group)
                if times:
                    if date_str in slots_by_date:
                        slots_by_date[date_str].extend(times)
                    else:
                        slots_by_date[date_str] = times
                    logger.debug(f"Found {len(times)} slots for {date_str}")

            except Exception as e:
                logger.error(f"Error processing date group {i}: {e}")
                continue

    except Exception as e:
        logger.error(f"Error collecting time slots: {e}")

    # Remove duplicates and sort times
    for date_str in slots_by_date:
        slots_by_date[date_str] = sorted(list(set(slots_by_date[date_str])))

    return slots_by_date


def _extract_date_from_group(group) -> Optional[str]:
    """
    Extract date string from a DateTimeGrouping-Group element.

    Returns:
        Date string in YYYY-MM-DD format, or None if not found
    """
    try:
        # Look for date in various common formats
        # Try to find date label or header within the group
        date_text = None

        # Strategy 1: Look for common date label selectors
        for selector in ['.date-label', '.date-header', 'label', 'h3', 'h4', '.DateTimeGrouping-Date']:
            try:
                element = group.locator(selector).first
                if element.is_visible():
                    date_text = element.inner_text().strip()
                    break
            except:
                continue

        # Strategy 2: Get all text and try to parse
        if not date_text:
            date_text = group.inner_text().split('\n')[0].strip()

        if date_text:
            # Try to parse date
            parsed_date = _parse_date_string(date_text)
            if parsed_date:
                return parsed_date

    except Exception as e:
        logger.error(f"Error extracting date: {e}")

    return None


def _parse_date_string(date_text: str) -> Optional[str]:
    """
    Parse various date formats to YYYY-MM-DD.

    Args:
        date_text: Date string in various formats

    Returns:
        Date string in YYYY-MM-DD format
    """
    try:
        # Remove common prefixes
        date_text = date_text.replace('Date:', '').replace('date:', '').strip()

        # Try different date formats
        formats = [
            '%B %d, %Y',      # November 8, 2025
            '%b %d, %Y',      # Nov 8, 2025
            '%m/%d/%Y',       # 11/08/2025
            '%Y-%m-%d',       # 2025-11-08
            '%A, %B %d, %Y',  # Friday, November 8, 2025
            '%A, %b %d, %Y',  # Friday, Nov 8, 2025
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_text, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_text}")
        return None

    except Exception as e:
        logger.error(f"Error parsing date '{date_text}': {e}")
        return None


def _extract_times_from_group(group) -> List[str]:
    """
    Extract time slots from a DateTimeGrouping-Group element.

    Returns:
        List of time strings (e.g., ["09:00 AM", "10:00 AM"])
    """
    times = []

    try:
        # Look for time elements - common selectors for time slots
        time_selectors = [
            '.time-slot',
            '.appointment-time',
            'input[type="radio"][value*=":"]',
            'label:has(input[type="radio"])',
            '.DateTimeGrouping-Time',
            'button:has-text("M")',  # Contains AM/PM
        ]

        for selector in time_selectors:
            try:
                elements = group.locator(selector).all()
                for element in elements:
                    try:
                        text = element.inner_text().strip()
                        # Look for time pattern (HH:MM AM/PM)
                        if ':' in text and ('AM' in text or 'PM' in text):
                            # Extract just the time portion
                            time_part = text.split('\n')[0].strip()
                            if time_part not in times:
                                times.append(time_part)
                    except:
                        continue

                if times:
                    break  # Found times with this selector
            except:
                continue

        # If no times found with specific selectors, try parsing all text
        if not times:
            try:
                all_text = group.inner_text()
                # Look for time patterns in the text
                import re
                time_pattern = r'\d{1,2}:\d{2}\s*(?:AM|PM)'
                matches = re.findall(time_pattern, all_text, re.IGNORECASE)
                times.extend([m.strip().upper() for m in matches])
            except:
                pass

    except Exception as e:
        logger.error(f"Error extracting times: {e}")

    return times


# Legacy functions (kept for compatibility)

def init_browser():
    """Initialize Playwright browser"""
    logger.info("Browser will be initialized on-demand")


def close_browser():
    """Close the browser instance"""
    logger.info("Browser closed (handled by context manager)")


def get_page() -> Optional[Page]:
    """Get a new browser page"""
    # Not used in new implementation - handled internally
    pass


def scrape_url(url: str) -> Dict[str, Any]:
    """Scrape a URL and extract data"""
    return scrape_appointment_slots(url)


def extract_data(page: Page) -> Dict[str, Any]:
    """Extract data from a page"""
    return _collect_time_slots(page)


def wait_for_page_load(page: Page):
    """Wait for page to fully load"""
    page.wait_for_load_state('domcontentloaded')
    time.sleep(1)


def take_screenshot(page: Page, filename: str):
    """Take a screenshot of the current page"""
    try:
        page.screenshot(path=filename)
        logger.info(f"Screenshot saved to {filename}")
    except Exception as e:
        logger.error(f"Failed to take screenshot: {e}")


def scrape_with_retry(url: str, max_retries: int = 3) -> Dict[str, Any]:
    """Scrape with retry logic"""
    for attempt in range(max_retries):
        try:
            return scrape_appointment_slots(url)
        except Exception as e:
            logger.warning(f"Scrape attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise


def cleanup():
    """Cleanup browser resources"""
    logger.info("Cleanup complete (handled by context manager)")
