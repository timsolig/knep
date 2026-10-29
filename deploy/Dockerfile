# Driften: hela prognoskedjan i en container (arm64). Byggs och startas av deploy/compose.yaml.
FROM python:3.12-slim-bookworm AS bygg
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /usr/local/bin/uv
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PYTHON=/usr/local/bin/python3
WORKDIR /app

# Beroendena först, så att de bara byggs om när uv.lock ändras (pysteps kompileras här)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src src
RUN uv sync --frozen --no-dev --no-editable

# De låsta modellversionerna från GitHub Releases, kontrollerade mot sha256 i models.json
COPY models/models.json models/
RUN .venv/bin/knep-models fetch

FROM python:3.12-slim-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git libgomp1 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=bygg /app/.venv .venv
COPY --from=bygg /app/models models
COPY deploy/loop.sh deploy/publish.sh deploy/
ENV PATH=/app/.venv/bin:$PATH
RUN useradd -m knep && mkdir cache out && chown knep cache out
USER knep
CMD ["deploy/loop.sh"]
