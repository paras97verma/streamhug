# Dockerfile for FastAPI Backend
FROM python:3.13-slim

# Install system dependencies (ffmpeg, nodejs, npm are critical)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    nodejs \
    npm \
    && npm install -g tunnelmole \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install from root context
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code from root context
COPY backend/ .

# Expose port
EXPOSE 8080

# Run uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
