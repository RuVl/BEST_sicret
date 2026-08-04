FROM docker.io/library/python:3.12-slim
LABEL authors="SPb BEST"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV TZ="Europe/Moscow"
ENV PIP_ROOT_USER_ACTION=ignore
ENV PYTHONUNBUFFERED=1
ENV UV_NO_CACHE=1

WORKDIR /app

# `uv sync` ставит зависимости в /app/.venv (UV_SYSTEM_PYTHON влияет только на `uv pip`),
# поэтому кладём venv в PATH — иначе alembic/python3 не находятся в контейнере.
ENV PATH="/app/.venv/bin:$PATH"

# Dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . ./

ENTRYPOINT ["alembic"]
CMD ["upgrade", "head"]
