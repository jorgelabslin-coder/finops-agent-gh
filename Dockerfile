FROM python:3.12-slim

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install --with-deps chromium \
    && chmod -R a+rX /ms-playwright

COPY --chown=appuser:appuser . .

RUN mkdir -p /app/data && chown appuser:appuser /app/data

VOLUME ["/app/data"]

USER appuser

ENTRYPOINT ["python", "src/main.py"]
