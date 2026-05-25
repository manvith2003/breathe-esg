FROM python:3.10-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps — path relative to repo root
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# Collect static files
RUN SECRET_KEY=build-dummy-key python manage.py collectstatic --noinput

# Media dir
RUN mkdir -p media/uploads

EXPOSE ${PORT:-8000}

CMD python manage.py migrate --noinput && \
    python manage.py loaddata emission_factors && \
    python manage.py seed_demo_data && \
    gunicorn breathe.wsgi:application \
      --bind 0.0.0.0:${PORT:-8000} \
      --workers 2 \
      --timeout 120 \
      --log-level info
