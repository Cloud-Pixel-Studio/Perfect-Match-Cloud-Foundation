# Preserve the official PostgreSQL entrypoint and data layout while refreshing
# Alpine packages and replacing the Go-based privilege switch with Alpine su-exec.
FROM postgres:18-alpine@sha256:10a5c69a83035ab5239f5620d708520e8b28f5aa1f2b20143e6024532edadfb5

RUN apk upgrade --no-cache \
    && apk add --no-cache su-exec \
    && rm /usr/local/bin/gosu \
    && sed -i 's/exec gosu postgres/exec su-exec postgres/g' /usr/local/bin/docker-entrypoint.sh \
    && test "$(su-exec postgres id -un)" = postgres \
    && ! grep -q 'exec gosu' /usr/local/bin/docker-entrypoint.sh

USER postgres
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 \
    CMD pg_isready -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}" || exit 1
