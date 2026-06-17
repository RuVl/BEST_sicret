FROM docker.io/library/python:3.12-slim
LABEL authors="SPb BEST"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV TZ="Europe/Moscow"
ENV PIP_ROOT_USER_ACTION=ignore
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . ./

ENTRYPOINT ["alembic"]
CMD ["upgrade", "head"]
