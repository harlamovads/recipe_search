FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV MODULE_NAME=app.api
ENV VARIABLE_NAME=app
ENV PORT=8000

# Expose port
EXPOSE 8000

# Use a shell form of CMD to ensure proper signal handling
CMD uvicorn ${MODULE_NAME}:${VARIABLE_NAME} --host 0.0.0.0 --port ${PORT} --log-level info