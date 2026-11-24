# Multi-stage production container image for ALOS runtime and compute governor.
# Spec: specs/034-portable-production-runtime/spec.md (FR-008)
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build
COPY pyproject.toml README.md ./
# Cache third-party dependencies separately so source edits rebuild in <2s without pip churn.
RUN mkdir -p alos && touch alos/__init__.py \
    && pip install --no-cache-dir --root-user-action=ignore --prefix=/install . \
    && rm -rf alos

COPY alos/ alos/
RUN pip install --no-cache-dir --root-user-action=ignore --no-deps --prefix=/install .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ALOS_HOME=/data \
    ALOS_SWARM_OLLAMA=http://host.docker.internal:11434

WORKDIR /app
RUN groupadd --gid 10001 alos \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin alos \
    && mkdir -p /data \
    && chown -R 10001:10001 /app /data

COPY --from=builder /install /usr/local
COPY --chown=10001:10001 alembic.ini ./
COPY --chown=10001:10001 alembic/ alembic/
COPY --chown=10001:10001 .specify/ .specify/

USER 10001:10001
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["alos", "doctor", "--json"]

ENTRYPOINT ["alos"]
CMD ["daemon", "--poll-s", "2.0"]
