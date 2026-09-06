FROM node:24.20.0-alpine@sha256:e67514e5d0f6c46656005e1b693b2ec9d52e80b641307de684d4a015ba7a4eaf AS dependencies
ENV NEXT_TELEMETRY_DISABLED=1
WORKDIR /workspace
RUN corepack enable
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/design-system/package.json packages/design-system/package.json
RUN pnpm install --frozen-lockfile

FROM dependencies AS build
COPY apps/web apps/web
COPY packages/design-system packages/design-system
RUN pnpm --filter @perfect-match/web build

FROM node:24.20.0-alpine@sha256:e67514e5d0f6c46656005e1b693b2ec9d52e80b641307de684d4a015ba7a4eaf AS runtime-base
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
WORKDIR /app
RUN apk upgrade --no-cache \
    && addgroup --system --gid 10001 pmcloud \
    && adduser --system --uid 10001 --ingroup pmcloud pmcloud \
    && rm -rf /usr/local/lib/node_modules/npm \
        /usr/local/lib/node_modules/corepack \
        /usr/local/bin/npm \
        /usr/local/bin/npx \
        /usr/local/bin/corepack \
        /usr/local/bin/pnpm \
        /usr/local/bin/pnpx
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000').then(r => { if (!r.ok) process.exit(1) }).catch(() => process.exit(1))"

FROM runtime-base AS runtime
COPY --from=build --chown=pmcloud:pmcloud /workspace/apps/web/.next/standalone ./
COPY --from=build --chown=pmcloud:pmcloud /workspace/apps/web/.next/static ./apps/web/.next/static
COPY --from=build --chown=pmcloud:pmcloud /workspace/apps/web/public ./apps/web/public
USER pmcloud
EXPOSE 3000
CMD ["node", "apps/web/server.js"]

FROM runtime-base AS runtime-offline
COPY --chown=pmcloud:pmcloud apps/web/prebuilt.tar /tmp/prebuilt.tar
RUN tar -xf /tmp/prebuilt.tar -C /app \
    && rm /tmp/prebuilt.tar
USER pmcloud
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
