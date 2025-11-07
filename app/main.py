"""Main Flask application entry point"""

import os
import logging
import hashlib
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
from sqlmodel import select

from app import scraper, notifier, reporter, persistence, timeutils
from app.models import Settings, CheckRun, AppointmentSlot, AlertSent

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize scheduler
scheduler = BackgroundScheduler()


def init_app():
    """Initialize the application"""
    # Initialize database (downloads from GCS if enabled)
    persistence.init_database()
    logger.info("Application initialized")


def setup_scheduler():
    """Setup scheduled jobs"""
    pass


def start_scheduler():
    """Start the background scheduler"""
    pass


def stop_scheduler():
    """Stop the background scheduler"""
    pass


def compute_fingerprint(location: str, date: str, times: list) -> str:
    """
    Compute SHA256 fingerprint for a location-date-times combination.

    Args:
        location: Location name
        date: Date string (YYYY-MM-DD)
        times: List of time strings

    Returns:
        SHA256 hex digest
    """
    sorted_times = sorted(times)
    fingerprint_str = f"{location}|{date}|{sorted_times}"
    return hashlib.sha256(fingerprint_str.encode()).hexdigest()


@app.route('/')
def index():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "rmv-watcher"})


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})


@app.route('/status')
def status():
    """Get current application status"""
    return jsonify({"status": "running"})


@app.route('/run-watcher', methods=['POST'])
def run_watcher():
    """
    Main watcher endpoint:
    1. Read Settings for appointment link
    2. Scrape appointment slots
    3. Filter to next 14 days
    4. Persist CheckRun and slots
    5. Compute fingerprints per location per date
    6. Check for new fingerprints
    7. Send single email with all new slots
    8. Store fingerprints in AlertSent
    """
    try:
        logger.info("Starting watcher run")

        # 1. Read Settings
        with persistence.get_session() as session:
            settings = session.get(Settings, 1)

            if not settings or not settings.appointment_link:
                logger.error("No appointment link configured in Settings")
                return jsonify({
                    "status": "error",
                    "message": "No appointment link configured"
                }), 400

            appointment_link = settings.appointment_link
            expires_at = settings.expires_at
            logger.info(f"Using appointment link: {appointment_link}")

        # 2. Create CheckRun record
        check_run = CheckRun(
            started_at=datetime.utcnow(),
            status="pending"
        )
        check_run = persistence.save_check_run(check_run)
        logger.info(f"Created CheckRun {check_run.id}")

        # 3. Scrape appointment slots
        try:
            scraped_slots = scraper.scrape_appointment_slots(appointment_link)
            logger.info(f"Scraped {len(scraped_slots)} locations")
        except Exception as e:
            logger.error(f"Scraping failed: {e}", exc_info=True)
            # Update CheckRun as failed
            with persistence.get_session() as session:
                run = session.get(CheckRun, check_run.id)
                run.status = "failed"
                run.error_message = str(e)
                run.completed_at = datetime.utcnow()

            return jsonify({
                "status": "error",
                "message": f"Scraping failed: {str(e)}"
            }), 500

        # 4. Filter to next 14 days
        filtered_dict, slot_dicts = timeutils.filter_slots_by_14_days(scraped_slots)
        logger.info(f"Filtered to {len(slot_dicts)} slots within 14 days")

        # 5. Convert to AppointmentSlot models and persist
        slots = timeutils.convert_to_appointment_slots(filtered_dict, check_run.id)
        if slots:
            persistence.save_slots(slots)
            logger.info(f"Saved {len(slots)} slots to database")

        # Update CheckRun
        with persistence.get_session() as session:
            run = session.get(CheckRun, check_run.id)
            run.status = "success"
            run.completed_at = datetime.utcnow()
            run.slots_found = len(slots)

        # 6. Compute fingerprints and check for new ones
        new_slots_by_location = {}
        fingerprints_to_save = []

        for location, dates in filtered_dict.items():
            location_has_new = False
            location_dates = {}

            for date_str, datetimes in dates.items():
                # Get time strings for fingerprint
                time_strs = [dt.strftime('%I:%M %p') for dt in datetimes]
                fingerprint = compute_fingerprint(location, date_str, time_strs)

                # Check if this fingerprint already exists
                if not persistence.has_fingerprint(fingerprint):
                    # New slots!
                    location_dates[date_str] = datetimes
                    location_has_new = True
                    fingerprints_to_save.append((fingerprint, location, date_str))
                    logger.info(f"New slots found: {location} on {date_str}")
                else:
                    logger.info(f"Skipping duplicate: {location} on {date_str}")

            if location_has_new:
                new_slots_by_location[location] = location_dates

        # 7. Send email if we have new slots
        if new_slots_by_location:
            logger.info(f"Sending alert email for {len(new_slots_by_location)} location(s)")
            try:
                notifier.send_alert_email(new_slots_by_location, appointment_link, expires_at)

                # 8. Store fingerprints in AlertSent
                for fingerprint, location, date_str in fingerprints_to_save:
                    persistence.record_alert_fingerprint(
                        fingerprint=fingerprint,
                        check_run_id=check_run.id,
                        alert_type="email"
                    )
                logger.info(f"Saved {len(fingerprints_to_save)} fingerprints")

            except Exception as e:
                logger.error(f"Failed to send email: {e}", exc_info=True)
                return jsonify({
                    "status": "partial_success",
                    "message": "Slots found but email failed",
                    "check_run_id": check_run.id,
                    "slots_found": len(slots),
                    "new_slots": len(fingerprints_to_save),
                    "error": str(e)
                }), 500
        else:
            logger.info("No new slots found (all duplicates)")

        return jsonify({
            "status": "success",
            "check_run_id": check_run.id,
            "slots_found": len(slots),
            "new_slots": len(fingerprints_to_save),
            "email_sent": len(new_slots_by_location) > 0
        })

    except Exception as e:
        logger.error(f"Watcher run failed: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/run-reporter', methods=['POST'])
def run_reporter():
    """
    Generate and send daily report:
    1. Query today's CheckRuns and slots
    2. Build HTML summary with:
       - Earliest slot per location
       - Number of checks per location
       - List of <14-day slots seen today
       - Expiry countdown
    3. Email the report
    """
    try:
        logger.info("Starting reporter run")

        # Get Settings for expiry info
        with persistence.get_session() as session:
            settings = session.get(Settings, 1)
            expires_at = settings.expires_at if settings else None
            appointment_link = settings.appointment_link if settings else None

        # Query today's data
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        with persistence.get_session() as session:
            # Get today's check runs
            check_runs_stmt = select(CheckRun).where(
                CheckRun.started_at >= today_start,
                CheckRun.started_at < today_end
            )
            check_runs = session.exec(check_runs_stmt).all()

            # Get today's slots
            if check_runs:
                check_run_ids = [run.id for run in check_runs]
                slots_stmt = select(AppointmentSlot).where(
                    AppointmentSlot.check_run_id.in_(check_run_ids)
                )
                slots = session.exec(slots_stmt).all()
            else:
                slots = []

        logger.info(f"Found {len(check_runs)} check runs and {len(slots)} slots today")

        # Build HTML report
        html_report = _build_html_report(check_runs, slots, appointment_link, expires_at)

        # Send email
        try:
            subject = f"RMV Watcher Daily Report - {datetime.now().strftime('%Y-%m-%d')}"
            notifier.send_report_email(html_report, subject)
            logger.info("Report email sent successfully")

            return jsonify({
                "status": "success",
                "check_runs": len(check_runs),
                "slots": len(slots)
            })

        except Exception as e:
            logger.error(f"Failed to send report email: {e}", exc_info=True)
            return jsonify({
                "status": "error",
                "message": f"Failed to send report: {str(e)}"
            }), 500

    except Exception as e:
        logger.error(f"Reporter run failed: {e}", exc_info=True)
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


def _build_html_report(check_runs, slots, appointment_link, expires_at):
    """Build HTML report from check runs and slots"""

    # Organize slots by location
    slots_by_location = {}
    for slot in slots:
        if slot.location not in slots_by_location:
            slots_by_location[slot.location] = []
        slots_by_location[slot.location].append(slot)

    # Compute statistics
    stats = {}
    for location, location_slots in slots_by_location.items():
        earliest = min(location_slots, key=lambda s: s.slot_time) if location_slots else None
        stats[location] = {
            'earliest': earliest,
            'count': len(location_slots),
            'slots': sorted(location_slots, key=lambda s: s.slot_time)
        }

    # Build HTML
    html_parts = [
        '<html><head><style>',
        'body { font-family: Arial, sans-serif; margin: 20px; color: #333; }',
        'h1 { color: #2c5aa0; }',
        'h2 { color: #2c5aa0; border-bottom: 2px solid #2c5aa0; padding-bottom: 5px; }',
        'table { border-collapse: collapse; width: 100%; margin: 20px 0; }',
        'th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }',
        'th { background-color: #2c5aa0; color: white; }',
        'tr:nth-child(even) { background-color: #f2f2f2; }',
        '.stat-box { background: #e3f2fd; padding: 15px; margin: 10px 0; border-radius: 5px; }',
        '.warning { background: #fff3cd; padding: 10px; border-left: 4px solid #ffc107; margin: 10px 0; }',
        '.success { background: #d4edda; padding: 10px; border-left: 4px solid #28a745; margin: 10px 0; }',
        '</style></head><body>',
        f'<h1>RMV Watcher Daily Report - {datetime.now().strftime("%Y-%m-%d")}</h1>'
    ]

    # Summary stats
    html_parts.append('<h2>Summary</h2>')
    html_parts.append(f'<div class="stat-box">')
    html_parts.append(f'<p><strong>Check Runs Today:</strong> {len(check_runs)}</p>')
    html_parts.append(f'<p><strong>Total Slots Found:</strong> {len(slots)}</p>')
    html_parts.append(f'<p><strong>Locations Monitored:</strong> {len(slots_by_location)}</p>')

    if appointment_link:
        html_parts.append(f'<p><strong>Appointment Link:</strong> <a href="{appointment_link}">{appointment_link}</a></p>')

    if expires_at:
        now = datetime.utcnow()
        if expires_at > now:
            time_left = expires_at - now
            days = time_left.days
            hours = time_left.seconds // 3600
            html_parts.append(f'<div class="warning"><strong>⏰ Link Expires In:</strong> {days} days, {hours} hours</div>')
        else:
            html_parts.append(f'<div class="warning"><strong>⚠️ Link Expired</strong></div>')

    html_parts.append('</div>')

    # Earliest slot per location
    if stats:
        html_parts.append('<h2>Earliest Slot Per Location</h2>')
        html_parts.append('<table>')
        html_parts.append('<tr><th>Location</th><th>Earliest Slot</th><th>Total Slots</th></tr>')

        for location in sorted(stats.keys()):
            earliest = stats[location]['earliest']
            count = stats[location]['count']

            if earliest:
                slot_str = earliest.slot_time.strftime('%Y-%m-%d %I:%M %p')
                html_parts.append(f'<tr><td>{location}</td><td>{slot_str}</td><td>{count}</td></tr>')

        html_parts.append('</table>')

    # All slots within 14 days
    now_et = timeutils.get_current_et_time()
    cutoff = now_et + timedelta(days=14)

    future_slots = [s for s in slots if s.slot_time > now_et and s.slot_time <= cutoff]

    if future_slots:
        html_parts.append('<h2>All Slots Within Next 14 Days</h2>')
        html_parts.append('<table>')
        html_parts.append('<tr><th>Location</th><th>Date</th><th>Time</th><th>Days Away</th></tr>')

        for slot in sorted(future_slots, key=lambda s: s.slot_time):
            days_away = (slot.slot_time - now_et).days
            html_parts.append(f'<tr>')
            html_parts.append(f'<td>{slot.location}</td>')
            html_parts.append(f'<td>{slot.slot_time.strftime("%Y-%m-%d")}</td>')
            html_parts.append(f'<td>{slot.slot_time.strftime("%I:%M %p")}</td>')
            html_parts.append(f'<td>{days_away}</td>')
            html_parts.append(f'</tr>')

        html_parts.append('</table>')
    else:
        html_parts.append('<div class="warning">No slots found within the next 14 days.</div>')

    # Check run history
    if check_runs:
        html_parts.append('<h2>Check Run History (Today)</h2>')
        html_parts.append('<table>')
        html_parts.append('<tr><th>ID</th><th>Started At</th><th>Status</th><th>Slots Found</th></tr>')

        for run in sorted(check_runs, key=lambda r: r.started_at, reverse=True):
            html_parts.append(f'<tr>')
            html_parts.append(f'<td>{run.id}</td>')
            html_parts.append(f'<td>{run.started_at.strftime("%H:%M:%S")}</td>')
            html_parts.append(f'<td>{run.status}</td>')
            html_parts.append(f'<td>{run.slots_found}</td>')
            html_parts.append(f'</tr>')

        html_parts.append('</table>')

    html_parts.append('</body></html>')

    return ''.join(html_parts)


# Legacy endpoint for compatibility
@app.route('/trigger-scrape', methods=['POST'])
def trigger_scrape():
    """Manually trigger a scraping job (redirects to run-watcher)"""
    return run_watcher()


if __name__ == '__main__':
    init_app()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False') == 'True')
