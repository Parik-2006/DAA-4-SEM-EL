# Multi-stage Dockerfile for Smart Attendance System Backend

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libopenblas-dev \
    liblapack-dev \
    gfortran \
    libhdf5-dev \
    pkg-config \
    libglib2.0-0 \
    libglib2.0-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Build wheels for faster installation (large ML wheels need higher timeout/retries)
RUN pip wheel --no-cache-dir --no-deps --retries 20 --timeout 1000 --wheel-dir /build/wheels -r requirements.txt


# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libopenblas0 \
    liblapack3 \
    libgomp1 \
    libhdf5-310 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    libglib2.0-0 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder
COPY --from=builder /build/wheels /wheels
COPY requirements.txt .

# Install Python dependencies with increased timeout and retries
RUN pip install --no-cache --default-timeout=1000 --retries 5 /wheels/*

# Copy application code
COPY config ./config
COPY models ./models
COPY services ./services
COPY utils ./utils
COPY database ./database
COPY schemas ./schemas
COPY api ./api
COPY main.py .

# Create necessary directories
RUN mkdir -p logs weights indexes

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FASTAPI_ENV=production

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')"

# Run FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
