FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[api,loaders]"

COPY project ./project

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

ENV AIKIT_CONFIG=project/app.yaml
EXPOSE 8080

CMD ["aikit", "serve", "--host", "0.0.0.0", "--port", "8080"]
