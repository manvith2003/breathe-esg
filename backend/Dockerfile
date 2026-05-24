FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Build static files
RUN python manage.py collectstatic --noinput

# Create media directory
RUN mkdir -p media/uploads

EXPOSE 8000

CMD ["gunicorn", "breathe.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
