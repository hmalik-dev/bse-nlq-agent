# A local demo image: the built interface and the API in one container that
# seeds its own database on first start (see docker/entrypoint.sh). Plain by
# design: no health check, nothing production-shaped, but the server does not
# run as root (docs/security.md).

# Stage 1: build the web interface into src/nlq/static.
FROM node:24-alpine AS web
WORKDIR /build
COPY package.json package-lock.json ./
COPY web/package.json web/
RUN npm ci
COPY web web
RUN npm run -w web build

# Stage 2: the Python app, with the built interface copied in from stage 1.
FROM python:3.12-slim AS app
COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    NLQ_DATABASE_PATH=/data/tickets.db

# Dependencies first, so a source change does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src src
COPY --from=web /build/src/nlq/static src/nlq/static
RUN uv sync --frozen --no-dev

COPY docker/entrypoint.sh docker/entrypoint.sh
# The app files stay root-owned, so the server cannot rewrite them; only /data,
# where the database is seeded, belongs to it.
RUN useradd --system --no-create-home --uid 10001 nlq \
    && mkdir -p /data && chown nlq:nlq /data
USER nlq
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
