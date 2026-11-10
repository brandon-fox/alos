# Stay on a Python the dependencies publish wheels for; CI tests 3.11 to 3.13.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY alos/ alos/
COPY .specify/ .specify/

RUN pip install --no-cache-dir .

ENTRYPOINT ["python", "-m", "alos.cli"]
