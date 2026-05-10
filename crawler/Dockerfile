FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    crawl4ai \
    pyyaml \
    requests \
    python-dotenv \
    aiofiles

# Create data directories
RUN mkdir -p /data/output /data/cache /app/logs

# Volume mounts
VOLUME ["/data", "/app/logs"]

# Copy crawler script
COPY crawler.py /app/crawler.py
COPY sources.yaml /app/sources.yaml

# Run crawler
CMD ["python", "crawler.py"]
