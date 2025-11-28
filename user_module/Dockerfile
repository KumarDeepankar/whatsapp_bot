FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories
RUN mkdir -p /app/data /root/.aws

# Copy AWS credentials (create these files before building)
# Option 1: Copy credentials file directly (if exists)
COPY .aws/credentials /root/.aws/credentials
COPY .aws/config /root/.aws/config

# Expose port
EXPOSE 8009

# Run the application
CMD ["python", "run.py"]
