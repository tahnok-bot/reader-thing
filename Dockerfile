FROM ghcr.io/astral-sh/uv:python3.15-trixie-slim

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first, so code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

RUN useradd --uid 1000 --home-dir /data reader \
    && mkdir /data && chown reader /data
USER reader

# The SQLite database lives on a volume; everything else comes from the environment.
ENV PATH=/app/.venv/bin:$PATH DATABASE_PATH=/data/reader.db HOST=0.0.0.0 PORT=8000
VOLUME /data
EXPOSE 8000

CMD ["reader-thing", "serve"]
