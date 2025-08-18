# Stage 1: Install Python dependencies
FROM python:3.13.7-slim@sha256:27f90d79cc85e9b7b2560063ef44fa0e9eaae7a7c3f5a9f74563065c5477cc24 AS python-builder

WORKDIR /build

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends gcc python3-dev; \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY src/ ./src/

RUN set -eux; \
    pip install --no-cache-dir --upgrade pip; \
    pip install --no-cache-dir --timeout 1000 .[server,mcp]

# Stage 2: Runtime image
FROM python:3.13.7-slim@sha256:27f90d79cc85e9b7b2560063ef44fa0e9eaae7a7c3f5a9f74563065c5477cc24

ARG UID=1000
ARG GID=1000
ARG APP_REPOSITORY=https://github.com/coderamp-labs/gitingest
ARG APP_VERSION=unknown
ARG APP_VERSION_URL=https://github.com/coderamp-labs/gitingest

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_REPOSITORY=${APP_REPOSITORY} \
    APP_VERSION=${APP_VERSION} \
    APP_VERSION_URL=${APP_VERSION_URL}

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends git curl; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN set -eux; \
    groupadd -g "$GID" appuser; \
    useradd -m -u "$UID" -g "$GID" appuser

COPY --from=python-builder --chown=$UID:$GID /usr/local/lib/python3.13/site-packages/ /usr/local/lib/python3.13/site-packages/
COPY --chown=$UID:$GID src/ ./

RUN set -eux; \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
EXPOSE 9090
CMD ["python", "-m", "server"]
