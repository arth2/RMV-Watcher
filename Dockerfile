FROM python:3.11-slim

# System deps for Playwright/Chromium
RUN apt-get update && apt-get install -y \
    curl wget gnupg ca-certificates fonts-liberation \
    libnss3 libxkbcommon0 libasound2 libxcomposite1 libxrandr2 libxi6 \
    libglib2.0-0 libgtk-3-0 libxdamage1 libxtst6 libatk-bridge2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN pip install --no-cache-dir playwright && python -m playwright install --with-deps chromium

COPY . .

# Cloud Run expects the server to listen on $PORT
ENV PORT=8080
EXPOSE 8080

CMD ["python", "-m", "app.main"]
