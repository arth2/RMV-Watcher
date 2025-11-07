"""Main Flask application entry point"""

import os
from flask import Flask, jsonify
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

from app import scraper, notifier, reporter, persistence

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Initialize scheduler
scheduler = BackgroundScheduler()


def init_app():
    """Initialize the application"""
    # Initialize database (downloads from GCS if enabled)
    persistence.init_database()


def setup_scheduler():
    """Setup scheduled jobs"""
    pass


def start_scheduler():
    """Start the background scheduler"""
    pass


def stop_scheduler():
    """Stop the background scheduler"""
    pass


@app.route('/')
def index():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "rmv-watcher"})


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})


@app.route('/trigger-scrape', methods=['POST'])
def trigger_scrape():
    """Manually trigger a scraping job"""
    return jsonify({"message": "Scrape triggered"})


@app.route('/status')
def status():
    """Get current application status"""
    return jsonify({"status": "running"})


if __name__ == '__main__':
    init_app()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False') == 'True')
