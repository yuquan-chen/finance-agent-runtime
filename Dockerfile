FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8810

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-chi-sim \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src
COPY config ./config
COPY scripts ./scripts
COPY schema_catalog/demo_schema.yaml ./schema_catalog/demo_schema.yaml
RUN pip install --no-cache-dir .

RUN mkdir -p /app/data /app/schema_catalog
VOLUME ["/app/data"]

EXPOSE 8810

CMD ["./scripts/start.sh"]
