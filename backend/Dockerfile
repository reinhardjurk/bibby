FROM python:3.12-slim

# WeasyPrint braucht ein paar System-Libs (für die Startnummern-PDFs).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

# Build-Kennung (z. B. Git-Kurz-SHA) beim Bauen mitgeben:
#   docker build --build-arg BUILD=$(git rev-parse --short HEAD) ...
ARG BUILD=dev
ENV BIBBY_BUILD=$BUILD

# Scaleway Serverless Containers setzen $PORT; lokal Default 8000.
# Migrationen laufen NICHT beim Start (Serverless-Pooler + parallele Instanzen
# sind dafür ungeeignet); sie werden separat/manuell ausgeführt (siehe README).
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
