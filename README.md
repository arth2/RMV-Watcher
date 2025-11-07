# RMV-Watcher

A Python 3.11 Flask application for monitoring and scraping RMV websites with automated notifications.

## Project Structure

```
rmv-watcher/
├── app/
│   ├── __init__.py          # Package initialization
│   ├── main.py              # Flask application entry point
│   ├── scraper.py           # Web scraping with Playwright
│   ├── notifier.py          # Notification functionality
│   ├── reporter.py          # Reporting and analytics
│   ├── models.py            # Database models
│   ├── persistence.py       # Database operations
│   ├── link_manager.py      # Link management
│   ├── timeutils.py         # Time utilities
│   └── selectors.py         # CSS selectors
├── tests/                   # Test directory
├── requirements.txt         # Python dependencies
├── Dockerfile              # Docker configuration
├── .env.example            # Environment variables template
└── README.md               # This file
```

## Features

- Web scraping with Playwright
- Automated scheduling with APScheduler
- Database persistence with SQLModel
- Email and webhook notifications
- Report generation with Jinja2
- Cloud storage integration (Google Cloud Storage)
- RESTful API endpoints
- Docker support for deployment

## Requirements

- Python 3.11
- Docker (optional)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd rmv-watcher
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env with your configuration
```

## Usage

### Local Development

```bash
python -m app.main
```

### Docker

Build and run with Docker:
```bash
docker build -t rmv-watcher .
docker run -p 8080:8080 --env-file .env rmv-watcher
```

## API Endpoints

- `GET /` - Health check
- `GET /health` - Health status
- `POST /trigger-scrape` - Manually trigger scraping
- `GET /status` - Application status

## Configuration

See `.env.example` for all available configuration options.

## Development

This project uses:
- Flask for the web framework
- Playwright for web scraping
- SQLModel for database ORM
- APScheduler for task scheduling
- Pydantic for data validation

## License

TBD

## Contributing

TBD
