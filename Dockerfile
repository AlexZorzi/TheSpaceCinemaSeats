# Multi-stage build for minimal image size
FROM python:3.11-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    jpeg-dev \
    zlib-dev \
    freetype-dev \
    lcms2-dev \
    openjpeg-dev \
    tiff-dev \
    tk-dev \
    tcl-dev

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-alpine

# Install runtime dependencies only
RUN apk add --no-cache \
    jpeg \
    zlib \
    freetype \
    lcms2 \
    openjpeg \
    tiff \
    ttf-dejavu

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Create app directory
WORKDIR /app

# Copy application files
COPY TheSpaceCinema.py .
COPY tg.py .
COPY main.py .

# Create directory for database
RUN mkdir -p /app/data

# Run as non-root user
RUN adduser -D -u 1000 botuser && \
    chown -R botuser:botuser /app
USER botuser

# Set database path to persistent volume
ENV DB_PATH=/app/data/bookings.db

CMD ["python", "tg.py"]
