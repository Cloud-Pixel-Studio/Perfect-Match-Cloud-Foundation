FROM docker.io/astral/uv:0.12.10-python3.12-trixie@sha256:d6266fd06c07deff751ec9f579679a8f3c209c32494cbc4b947a2aa586762106 AS uv

FROM python:3.12-alpine@sha256:b64631e04e4920160c50fbe8d8df828f7f35f06f425cb44aa09bca53e708a35a AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_HTTP_TIMEOUT=120 \
    PATH="/app/.venv/bin:$PATH"

RUN apk upgrade --no-cache \
    && addgroup -S -g 10001 pmcloud \
    && adduser -S -D -H -u 10001 -G pmcloud pmcloud

WORKDIR /app
COPY --from=uv /usr/local/bin/uv /usr/local/bin/uvx /bin/
COPY pyproject.toml uv.lock requirements-runtime.txt ./
COPY vendor-wheels ./vendor-wheels
RUN if [ -f vendor-wheels/.complete ]; then \
      uv pip install --system --no-index --find-links=vendor-wheels -r requirements-runtime.txt; \
    else \
      uv sync --frozen --no-dev --no-install-project; \
    fi \
    && rm -rf vendor-wheels \
        /usr/local/lib/python3.12/site-packages/pip \
        /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
    && rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.12 \
        /bin/uv /bin/uvx
COPY src ./src
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

USER pmcloud
EXPOSE 8000
ENV PYTHONPATH=/app/src
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)" || exit 1
CMD ["uvicorn", "pmc_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
