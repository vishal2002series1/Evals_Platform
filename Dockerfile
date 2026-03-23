# Use Python 3.11 to match your working environment
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc g++ libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy the exact file
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir "langfuse<3.0.0" uvicorn

# Copy the rest of the application
COPY . .

# Set Python path so imports work correctly
ENV PYTHONPATH=/app