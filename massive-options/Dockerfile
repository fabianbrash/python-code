# Use a lightweight Python base image
FROM python:3.10-slim

# Set environment variables to ensure Python output is logged to the console
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create and set the working directory
WORKDIR /app

# Install system dependencies if needed (minimal for this app)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# We install these directly to keep the image simple for v0.0.1
RUN pip install --no-cache-dir \
    flask \
    polygon-api-client \
    pytz \
    gunicorn

# Copy the application code
COPY . .

# Expose the port the app runs on
EXPOSE 5001

# Use Gunicorn for a more stable "production" server than the Flask dev server
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "app:app"]
