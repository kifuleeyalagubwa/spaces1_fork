# Dockerfile - FIXED VERSION

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 django && chown -R django:django /app
USER django

# TEMPORARY: Skip collectstatic during build (causes Redis error)
# We'll run it at runtime instead
# RUN python manage.py collectstatic --noinput

# Run migrations and start server
CMD sh -c "python manage.py migrate --noinput && python manage.py collectstatic --noinput && gunicorn classroom.wsgi --bind 0.0.0.0:$PORT --workers 3 --timeout 120 --access-logfile -"