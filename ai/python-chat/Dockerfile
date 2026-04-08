# 1. Use a stable Python base image (slim version saves space)
FROM python:3.9-slim

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Copy requirements first (this optimizes build speed by caching layers)
COPY requirements.txt .

# 4. Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy your application files (app.py and the /templates folder)
COPY . .

# 6. Set Environment Variables
# We leave API_KEY empty here so you can pass it safely at runtime
ENV RAFAY_API_KEY=""
ENV FLASK_ENV=production

# 7. Expose the port the app listens on
EXPOSE 5001

# 8. Start the app with Gunicorn
# --workers 2 allows the app to handle multiple users simultaneously
# --bind 0.0.0.0:5001 makes it accessible outside the container
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "app:app"]
