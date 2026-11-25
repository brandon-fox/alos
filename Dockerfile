# Multi-stage locked production container image for ALOS runtime and compute governor.
# Spec: specs/034-portable-production-runtime/spec.md & specs/038-enterprise-cicd-pipeline/spec.md (FR-009)
FROM ghcr.io/astral-sh/uv:0.10 AS uv-bin

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY --from=uv-bin /uv /uvx /bin/
WORKDIR /build
COPY pyproject.toml uv.lock README.md ./
# Sync third-party dependencies strictly from uv.lock (--frozen) before copying source for layer caching.
RUN uv sync --frozen --no-dev --no-install-project

COPY alos/ alos/
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="alos" \
      org.opencontainers.image.description="Local Autonomous Life Operating System (ALOS)" \
      org.opencontainers.image.source="https://github.com/brandon-fox/alos" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    ALOS_HOME=/data \
    ALOS_SWARM_OLLAMA=http://host.docker.internal:11434

WORKDIR /app
RUN groupadd --gid 10001 alos \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin alos \
    && mkdir -p /data \
    && chown -R 10001:10001 /app /data

COPY --from=builder /opt/venv /opt/venv
COPY --chown=10001:10001 alembic.ini ./
COPY --chown=10001:10001 alembic/ alembic/
COPY --chown=10001:10001 .specify/ .specify/

USER 10001:10001
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["alos", "doctor", "--json"]

ENTRYPOINT ["alos"]
CMD ["daemon", "--poll-s", "2.0"]
