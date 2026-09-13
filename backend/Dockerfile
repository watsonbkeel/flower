FROM python:3.13.7-slim-trixie
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client-17 && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home flower
COPY . .
USER 10001:10001
CMD ["uvicorn", "flower.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
