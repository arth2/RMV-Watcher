# RMV Watcher - Development Progress

## Project Overview

**Goal**: Build a Python 3.11 Flask application to monitor RMV (Registry of Motor Vehicles) appointment availability and send email alerts for new slots.

**Key Features**:
- Web scraping with Playwright to extract appointment slots
- Smart deduplication using SHA256 fingerprinting
- Email notifications via Gmail SMTP
- 14-day sliding window filtering in Eastern Time
- SQLite persistence with optional Google Cloud Storage sync
- Daily HTML reports
- Management commands for configuration

---

## Technical Approach

### Architecture Decisions

1. **Web Scraping**: Playwright Chromium for headless browser automation
   - Handles dynamic JavaScript content
   - Supports multiple selector strategies for robustness
   - Expands accordion/radio elements to reveal hidden times

2. **Timezone Handling**: Eastern Time (America/New_York) with pytz
   - All appointment times parsed and stored in ET
   - Proper DST (Daylight Saving Time) handling
   - Timezone-aware datetime objects throughout

3. **Deduplication Strategy**: SHA256 fingerprinting
   - Formula: `sha256(f"{location}|{date}|{sorted(times)}")`
   - Detects changes when slots are added or removed
   - Prevents duplicate alerts for unchanged availability
   - Fingerprints stored in AlertSent table

4. **Database**: SQLModel + SQLite
   - Local storage at `/tmp/state.sqlite3`
   - Optional GCS sync for persistence across container restarts
   - Four main tables: Settings, CheckRun, AppointmentSlot, AlertSent

5. **Email Notifications**: Gmail SMTP with TLS (port 587)
   - Multipart MIME emails (HTML + plain text)
   - Grouped by location and date for readability
   - Styled HTML with badge-based time display

---

## Development Timeline

### Phase 1: Project Scaffolding ✅
**Completed**: Initial setup

Created project structure with empty function stubs:
```
RMV-Watcher/
├── app/
│   ├── __init__.py
│   ├── main.py              # Flask app and endpoints
│   ├── scraper.py           # Playwright web scraper
│   ├── notifier.py          # Email notification system
│   ├── reporter.py          # Daily report generation
│   ├── models.py            # SQLModel database models
│   ├── persistence.py       # Database operations + GCS sync
│   ├── link_manager.py      # CLI commands for settings
│   ├── timeutils.py         # Timezone and date filtering
│   └── selectors.py         # CSS/XPath selectors
├── tests/
│   ├── __init__.py
│   ├── fixtures/            # Static HTML for testing
│   ├── test_timeutils.py
│   ├── test_fingerprinting.py
│   └── test_scraper.py
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

**Key Files**:
- `requirements.txt`: All Python dependencies specified
- `Dockerfile`: Container setup with Playwright Chromium installation
- `.env.example`: Environment variable template

---

### Phase 2: Database Layer ✅
**Completed**: Models and persistence

#### Database Models (app/models.py)

1. **Settings** (Singleton, id=1)
   - `appointment_link`: URL to scrape
   - `expires_at`: Link expiration datetime (ET)
   - Used by watcher to know what URL to scrape

2. **CheckRun**
   - Tracks each scraping execution
   - Fields: `started_at`, `completed_at`, `status`, `error_message`, `slots_found`

3. **AppointmentSlot**
   - Individual time slots found
   - Fields: `check_run_id` (FK), `slot_time`, `location`, `details`
   - Timezone-aware `slot_time` field

4. **AlertSent**
   - Deduplication tracking
   - Fields: `fingerprint` (unique), `check_run_id` (FK), `sent_at`, `alert_type`
   - Prevents sending duplicate alerts

#### Persistence Layer (app/persistence.py)

**Key Functions**:
- `get_db()`: Initialize SQLite engine, create tables
- `get_session()`: Context manager for DB sessions with auto-commit
- `save_check_run()`: Persist scraping run metadata
- `save_slots()`: Bulk save appointment slots
- `has_fingerprint()`: Check if alert already sent
- `record_alert_fingerprint()`: Store fingerprint after sending alert

**GCS Integration**:
- `download_from_gcs()`: Pull state.sqlite3 on startup (if USE_GCS_STORAGE=true)
- `upload_to_gcs()`: Push state.sqlite3 after commits
- Enables stateless container deployments

**Database Path**: `/tmp/state.sqlite3`

---

### Phase 3: Email Notifications ✅
**Completed**: Gmail SMTP integration

#### Implementation (app/notifier.py)

**Configuration** (Environment Variables):
- `EMAIL_HOST`: smtp.gmail.com (default)
- `EMAIL_PORT`: 587 (TLS)
- `EMAIL_USER`: Gmail address
- `EMAIL_PASSWORD`: App-specific password
- `EMAIL_FROM`: Sender address
- `EMAIL_TO`: Recipient address(s)

**Functions**:

1. **send_alert_email(grouped_slots, link, expires_at)**
   - Formats slots grouped by location and date
   - Shows all times for each date
   - Plain text: 6 times per row
   - HTML: Styled badges with hover effects
   - Includes appointment link and expiration countdown

2. **send_report_email(html_report)**
   - Sends daily summary report
   - Multipart MIME (HTML + plain text fallback)

**Email Format Example**:
```
Subject: New RMV Appointment Slots Available!

Watertown:
  November 8, 2025: 09:00 AM, 10:30 AM, 02:00 PM, 04:15 PM
  November 10, 2025: 11:00 AM, 01:30 PM, 03:45 PM

Haymarket:
  November 9, 2025: 09:30 AM, 11:00 AM
```

---

### Phase 4: Web Scraper ✅
**Completed**: Playwright-based scraper

#### Implementation (app/scraper.py)

**Target Locations**: Watertown, Haymarket, Wilmington

**Scraping Workflow**:
1. Launch headless Chromium browser
2. Navigate to appointment link
3. For each target location:
   - Click into location (exact name match)
   - Find all `.DateTimeGrouping-Group` elements
   - Expand each group (radio/accordion click)
   - Extract date and times
   - Return to list view
4. Return structured data: `{location: {"YYYY-MM-DD": ["HH:MM AM/PM", ...], ...}, ...}`

**Selector Strategies** (Robust fallbacks):
- Role-based: `page.get_by_role('button', name=location)`
- Link-based: `page.get_by_role('link', name=location)`
- Text locator: `page.get_by_text(location, exact=True)`

**Date Parsing** (Multiple formats supported):
- "November 8, 2025"
- "Nov 8, 2025"
- "11/08/2025"
- "2025-11-08"
- With weekdays: "Friday, November 8, 2025"
- With prefixes: "Date: November 8, 2025"

**Time Extraction**:
- Locates `.time-slot` elements
- Cleans whitespace
- Deduplicates times
- Returns sorted list per date

**Key Functions**:
- `scrape_appointment_slots(link)`: Main entry point
- `_scrape_location(page, location, link)`: Per-location scraping
- `_collect_time_slots(page)`: Extract all date/time pairs
- `_extract_date_from_group(group)`: Parse date from HTML
- `_extract_times_from_group(group)`: Parse times from HTML
- `_parse_date_string(date_str)`: Normalize date formats to YYYY-MM-DD

---

### Phase 5: Time Utilities ✅
**Completed**: ET timezone handling and filtering

#### Implementation (app/timeutils.py)

**Timezone**: `America/New_York` (Eastern Time with DST support)

**Key Functions**:

1. **get_current_et_time()**
   - Returns current time in ET timezone
   - Timezone-aware datetime object

2. **parse_appointment_datetime(date_str, time_str)**
   - Parses "YYYY-MM-DD" + "HH:MM AM/PM" into ET datetime
   - Returns timezone-aware datetime
   - Example: `("2025-11-08", "09:00 AM")` → `2025-11-08 09:00:00-05:00`

3. **filter_slots_by_14_days(scraped_slots)**
   - Filters to slots where: `now <= slot_time <= now + 14 days`
   - Inclusive boundary (exactly 14 days out is included)
   - Returns tuple:
     - Filtered dict: `{location: {"YYYY-MM-DD": [datetime, ...], ...}, ...}`
     - Slot list: `[{"slot_time": dt, "location": str, "details": str}, ...]`

4. **convert_to_appointment_slots(filtered_dict, check_run_id)**
   - Converts filtered dict to AppointmentSlot model instances
   - Ready for database persistence

**Filtering Logic**:
```python
now = get_current_et_time()
cutoff = now + timedelta(days=14)
if now <= slot_dt <= cutoff:
    # Include slot
```

---

### Phase 6: Main Endpoints ✅
**Completed**: Flask routes and core workflow

#### Implementation (app/main.py)

**Endpoint 1: POST /run-watcher**

Complete scraping and alerting workflow:

1. **Read Settings**: Get `appointment_link` and `expires_at`
2. **Create CheckRun**: Track this execution
3. **Scrape**: Call `scraper.scrape_appointment_slots()`
4. **Filter**: Apply 14-day window via `filter_slots_by_14_days()`
5. **Persist**: Save CheckRun and AppointmentSlot records
6. **Compute Fingerprints**: Per location, per date
   ```python
   fingerprint = compute_fingerprint(location, date_str, time_strs)
   ```
7. **Check for New Slots**: `has_fingerprint()` for each fingerprint
8. **Send Alert**: Single email with all new slots (if any)
9. **Record Fingerprints**: Save to AlertSent table

**Deduplication Example**:
- First run: Find slots A, B, C → Send alert, store fingerprint
- Second run: Find slots A, B, C → Skip (fingerprint exists)
- Third run: Find slots A, B, C, D → Send alert for new combination, store new fingerprint

**Endpoint 2: POST /run-reporter**

Daily summary report:

1. **Query Today's Data**:
   - All CheckRuns from today (ET)
   - All AppointmentSlots from today's runs
   - Filter to slots < 14 days out

2. **Build HTML Summary**:
   - Earliest slot per location
   - Check count per location
   - Full list of available slots
   - Link expiration countdown

3. **Send Email**: Via `send_report_email()`

**Fingerprint Function** (app/main.py:54-58):
```python
def compute_fingerprint(location: str, date: str, times: list) -> str:
    sorted_times = sorted(times)
    fingerprint_str = f"{location}|{date}|{sorted_times}"
    return hashlib.sha256(fingerprint_str.encode()).hexdigest()
```

---

### Phase 7: Settings Management ✅
**Completed**: CLI commands

#### Implementation (app/link_manager.py)

**Command 1: set_link(link, expires)**
- Parses expiration datetime (ISO8601 or "YYYY-MM-DD HH:MM:SS")
- Localizes to ET timezone
- Creates or updates Settings record (id=1)
- Persists to database

**Command 2: show_settings()**
- Retrieves Settings record
- Displays:
  - Appointment link
  - Expiration time (formatted in ET)
  - Time remaining calculation
- Returns Settings object

**Usage Example**:
```python
# Set link and expiration
set_link(
    link="https://example.com/appointments",
    expires="2025-11-30 23:59:59"  # ET
)

# View current settings
settings = show_settings()
```

---

### Phase 8: Unit Tests ✅
**Completed**: Comprehensive test suite

#### Test Files Created

**1. tests/test_timeutils.py** (216 lines)

Tests timezone-aware datetime handling:

- **TestParseAppointmentDateTime**
  - Basic AM/PM parsing
  - Noon and midnight edge cases
  - Timezone awareness verification
  - Various date formats

- **TestFilterSlotsBy14Days**
  - Slots within 14 days are included
  - Slots beyond 14 days are excluded
  - Past slots are excluded
  - Boundary test: exactly 14 days (inclusive)
  - Multiple locations handling
  - Mixed valid/invalid dates
  - Timezone preservation in returned datetimes

- **TestConvertToAppointmentSlots**
  - Basic conversion to model instances
  - Multiple locations
  - Timezone preservation

- **TestGetCurrentETTime**
  - Returns timezone-aware datetime
  - Approximately current time

**2. tests/test_fingerprinting.py** (263 lines)

Tests SHA256 fingerprinting and deduplication:

- **TestComputeFingerprint**
  - Basic fingerprint computation
  - Deterministic (same inputs = same hash)
  - Order independent (times are sorted)
  - Different times → different hash
  - Different location → different hash
  - Different date → different hash
  - Algorithm verification: `sha256(f"{loc}|{date}|{sorted_times}}")`

- **TestFingerprintDeduplication**
  - Same slots don't trigger duplicate alerts
  - Additional slot triggers new alert
  - Removed slot triggers new alert
  - Different locations tracked independently
  - Different dates tracked independently

- **TestFingerprintPersistence**
  - Mock-based tests for `has_fingerprint()`
  - Mock-based tests for `record_alert_fingerprint()`

**3. tests/test_scraper.py** (243 lines)

Tests web scraper with static HTML fixtures:

- **TestParseDateString**
  - Long month format: "November 8, 2025"
  - Short month format: "Nov 12, 2025"
  - Slash format: "11/09/2025"
  - ISO format: "2025-11-08"
  - With weekdays: "Friday, November 8, 2025"
  - With prefixes: "Date: November 8, 2025"
  - Invalid dates return None

- **TestExtractDateFromGroup**
  - Extract dates from Watertown fixture
  - Extract dates from Haymarket fixture

- **TestExtractTimesFromGroup**
  - Extract times from Watertown fixture (4 times)
  - Extract times from Haymarket fixture (2 times)

- **TestCollectTimeSlots**
  - Collect all slots from Watertown (3 dates, 9 total slots)
  - Collect all slots from Haymarket (2 dates, 5 total slots)
  - Verify times are sorted
  - Verify no duplicates

**4. Static HTML Fixtures**

Created realistic test fixtures in `tests/fixtures/`:

- **watertown_slots.html**
  - 3 date groups
  - November 8, 2025: 4 time slots
  - November 10, 2025: 3 time slots
  - November 15, 2025: 2 time slots

- **haymarket_slots.html**
  - 2 date groups
  - November 9, 2025: 2 time slots (11/09/2025 format)
  - November 12, 2025: 3 time slots (Nov format)

**5. Updated requirements.txt**

Added test dependencies:
- `pytest==7.4.3`
- `pytest-mock==3.12.0`

#### Running Tests

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_timeutils.py

# Run with verbose output
pytest -v tests/

# Run with coverage
pytest --cov=app tests/
```

---

## Current Status

### ✅ Completed Components

1. **Project Structure**: All files and directories created
2. **Database Models**: Settings, CheckRun, AppointmentSlot, AlertSent
3. **Persistence Layer**: SQLite + optional GCS sync
4. **Email System**: Gmail SMTP with TLS, multipart MIME
5. **Web Scraper**: Playwright-based with multiple selector strategies
6. **Time Utilities**: ET timezone parsing and 14-day filtering
7. **Main Endpoints**: /run-watcher and /run-reporter
8. **Settings Management**: CLI commands for configuration
9. **Unit Tests**: Comprehensive test coverage with fixtures

### 📋 Test Coverage Summary

| Area | Status | Tests |
|------|--------|-------|
| Date/time parsing (ET) | ✅ Complete | 18 tests |
| 14-day window filtering | ✅ Complete | 12 tests |
| Fingerprinting/dedup | ✅ Complete | 20+ tests |
| Scraper HTML parsing | ✅ Complete | 15+ tests |
| Static fixtures | ✅ Complete | 2 HTML files |

### 🔧 Configuration Required

Before running the application, configure these environment variables:

**Required**:
- `EMAIL_USER`: Gmail address
- `EMAIL_PASSWORD`: Gmail app-specific password
- `EMAIL_FROM`: Sender email address
- `EMAIL_TO`: Recipient email address(es)

**Optional**:
- `USE_GCS_STORAGE`: Set to 'true' for GCS sync (default: false)
- `GCS_BUCKET`: Bucket name for state.sqlite3 storage
- `GCS_CREDENTIALS_PATH`: Path to GCS service account JSON
- `HEADLESS_MODE`: Set to 'false' to see browser during scraping (default: true)

---

## Next Steps / Future Enhancements

### Immediate Tasks
- [ ] Manual testing of complete workflow
- [ ] Set up scheduled jobs (APScheduler)
- [ ] Configure environment variables for deployment
- [ ] Test GCS integration (if needed)

### Potential Enhancements
- [ ] Add more RMV locations beyond Watertown/Haymarket/Wilmington
- [ ] Support additional notification channels (SMS, Slack, etc.)
- [ ] Add web UI for viewing appointment history
- [ ] Implement rate limiting for scraper
- [ ] Add retry logic for failed scrapes
- [ ] Create Docker Compose setup for local development
- [ ] Add integration tests with real database
- [ ] Implement logging and monitoring
- [ ] Add health check endpoint
- [ ] Support custom alert filters (specific dates, times of day, etc.)

---

## Known Issues / Limitations

### Current Limitations
1. **Target Locations**: Hardcoded to 3 locations (Watertown, Haymarket, Wilmington)
2. **Single Link**: Only one appointment link supported at a time (Settings singleton)
3. **Email Only**: No support for other notification channels yet
4. **No Retries**: Scraper doesn't retry on failures
5. **No Rate Limiting**: Could potentially hit rate limits on appointment website

### Technical Debt
- Some unit tests use mocks instead of real database (acceptable trade-off)
- Reporter HTML template is embedded in code (could be externalized)
- Error handling could be more granular
- No logging framework integrated yet

---

## Dependencies

### Core Dependencies
- `Flask==3.0.0`: Web framework
- `playwright==1.47.2`: Web scraping
- `SQLAlchemy==2.0.35`: ORM
- `SQLModel==0.0.16`: Pydantic + SQLAlchemy
- `pytz==2024.1`: Timezone handling
- `APScheduler==3.10.4`: Job scheduling
- `google-cloud-storage==2.18.2`: GCS integration

### Development Dependencies
- `pytest==7.4.3`: Testing framework
- `pytest-mock==3.12.0`: Mocking support

### System Dependencies (Docker)
- Chromium browser (for Playwright)
- Fonts and multimedia support (libglib, libnss3, etc.)

---

## Git Branch

**Current Branch**: `claude/setup-rmv-watcher-project-011CUuG6Ypy9jPrzWqJsKZxB`

**Recent Commits**:
1. `910e5fe` - Add comprehensive unit tests for RMV Watcher
2. `5249d52` - Add settings management commands to link_manager.py
3. `586fbfc` - Implement main watcher and reporter endpoints with complete workflow
4. `c4c9f0b` - Implement time parsing and filtering utilities for ET timezone
5. `c77ea92` - Implement Playwright web scraper for RMV appointment slots

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     Flask Application                    │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  POST /run-watcher          POST /run-reporter           │
│  ┌─────────────────┐        ┌──────────────────┐        │
│  │ 1. Get Settings │        │ 1. Query Today's │        │
│  │ 2. Scrape Slots │        │    CheckRuns     │        │
│  │ 3. Filter (14d) │        │ 2. Build HTML    │        │
│  │ 4. Check Fingerprints    │ 3. Send Email    │        │
│  │ 5. Send Alerts  │        └──────────────────┘        │
│  │ 6. Save State   │                                     │
│  └─────────────────┘                                     │
│                                                           │
├───────────────┬─────────────┬──────────────┬────────────┤
│   scraper.py  │ timeutils.py│ notifier.py  │ models.py  │
│  (Playwright) │  (pytz/ET)  │ (SMTP/TLS)   │ (SQLModel) │
└───────────────┴─────────────┴──────────────┴────────────┘
                │             │              │
                ▼             ▼              ▼
         ┌──────────┐   ┌─────────┐   ┌──────────────┐
         │ RMV Site │   │ ET Time │   │ Gmail SMTP   │
         │ (scrape) │   │  (now)  │   │  (TLS:587)   │
         └──────────┘   └─────────┘   └──────────────┘

                        ▼
            ┌────────────────────────┐
            │   /tmp/state.sqlite3   │
            │  ┌──────────────────┐  │
            │  │ Settings (id=1)  │  │
            │  │ CheckRun         │  │
            │  │ AppointmentSlot  │  │
            │  │ AlertSent        │  │
            │  └──────────────────┘  │
            └────────────────────────┘
                        ▼
            ┌────────────────────────┐
            │ Google Cloud Storage   │
            │  (optional backup)     │
            └────────────────────────┘
```

---

## Summary

The RMV Watcher project is **functionally complete** with all core features implemented and tested:

✅ Web scraping with Playwright
✅ Smart deduplication via fingerprinting
✅ Email alerts with Gmail SMTP
✅ 14-day ET timezone filtering
✅ SQLite + optional GCS persistence
✅ Daily HTML reports
✅ Settings management
✅ Comprehensive unit tests

The application is ready for:
- Environment configuration
- Manual end-to-end testing
- Deployment to container platform
- Scheduled job setup (cron or APScheduler)

All code has been committed and pushed to the feature branch.
