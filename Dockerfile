FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY alos/ alos/
COPY .specify/ .specify/

RUN pip install --no-cache-dir .

RUN useradd -m alosuser && chown -R alosuser:alosuser /app
USER alosuser

ENTRYPOINT ["python", "-m", "alos.cli"]
