FROM docker.io/library/python:3.12-slim
LABEL authors="SPb BEST"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV TZ="Europe/Moscow"
ENV PYTHONUNBUFFERED=1
ENV UV_SYSTEM_PYTHON=1
ENV UV_NO_CACHE=1

WORKDIR /app

# Dependencies
COPY --from=database . ../packages/db
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Whole project
COPY . ./

ENTRYPOINT ["python3"]
CMD ["run.py"]

