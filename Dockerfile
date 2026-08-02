FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY alos/ alos/
COPY .specify/ .specify/

RUN pip install --no-cache-dir .

ENTRYPOINT ["python", "-m", "alos.cli"]
