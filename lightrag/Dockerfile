FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install LightRAG and dependencies
RUN pip install --no-cache-dir lightrag-hku flask flask-cors networkx openai tiktoken httpx beautifulsoup4 lxml

# Copy application files
COPY app.py /app/
COPY templates/ /app/templates/

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "-u", "app.py"]
