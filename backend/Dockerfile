FROM python:3.13.7-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home flower
COPY . .
USER 10001:10001
CMD ["uvicorn", "flower.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
