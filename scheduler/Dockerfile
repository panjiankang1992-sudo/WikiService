FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    apscheduler \
    pyyaml \
    requests \
    python-dotenv \
    watchdog \
    gitpython \
    aiofiles

# Create data directories
RUN mkdir -p /data /app/logs

# Copy scheduler and ingester
COPY scheduler.py /app/scheduler.py
COPY config.yaml /app/config.yaml
COPY ingester/ /app/ingester/

# Run scheduler
CMD ["python", "scheduler.py"]
