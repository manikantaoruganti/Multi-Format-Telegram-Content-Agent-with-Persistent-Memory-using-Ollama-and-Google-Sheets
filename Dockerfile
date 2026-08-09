# Use a production-ready Python base image
FROM python:3.11-slim-bookworm

# Set environment variables
ENV PYTHONUNBUFFERED 1
ENV APP_HOME /app

# Create app directory
WORKDIR $APP_HOME

# Install system dependencies required for markitdown and other packages
# libmagic-dev for python-magic (dependency of markitdown)
# poppler-utils for pdftotext (used by markitdown)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libmagic-dev \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ $APP_HOME/app/

# Create a non-root user
RUN adduser --system --group appuser
USER appuser

# Expose the health check port
EXPOSE 8080

# Command to run the application
CMD ["python", "app/main.py"]
