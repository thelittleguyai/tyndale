# syntax=docker/dockerfile:1
#
# Next.js admin console for the tyndale-dev-admin Container App (Phase CO-6A).
# Mirrors apps/web-marketing/Dockerfile. Build context: REPO ROOT so the npm
# workspace packages (@tyndale/shared) resolve at install + build time.
#   docker build -f apps/admin/Dockerfile -t IMAGE .

# ---- Stage 1: build ----------------------------------------------------------
FROM node:20-slim AS builder
WORKDIR /repo

ENV NEXT_TELEMETRY_DISABLED=1
# Build-only placeholder; the real AUTH_SECRET comes from the Container App env.
ENV AUTH_SECRET=build-only-placeholder-replaced-at-runtime-by-container-app-env

# NEXT_PUBLIC_* are inlined by `next build`, so they must be present at BUILD time.
ARG NEXT_PUBLIC_RUNTIME_URL=https://api.tyndaleapp.net
ARG NEXT_PUBLIC_PLAUSIBLE_DOMAIN=admin.tyndaleapp.net
ARG NEXT_PUBLIC_SIGNIN_URL=https://app.tyndaleapp.net/sign-in
ENV NEXT_PUBLIC_RUNTIME_URL=$NEXT_PUBLIC_RUNTIME_URL
ENV NEXT_PUBLIC_PLAUSIBLE_DOMAIN=$NEXT_PUBLIC_PLAUSIBLE_DOMAIN
ENV NEXT_PUBLIC_SIGNIN_URL=$NEXT_PUBLIC_SIGNIN_URL

COPY package.json package-lock.json tsconfig.base.json ./
COPY apps/admin/package.json apps/admin/
COPY packages/shared/package.json packages/shared/
RUN npm ci

COPY packages/shared packages/shared
COPY apps/admin apps/admin

RUN npm install --no-save --include=optional @next/swc-linux-x64-gnu @next/swc-linux-x64-musl || true

WORKDIR /repo/apps/admin
RUN sh -c 'npm run build 2>&1; status=$?; echo "--- next build exit status: $status ---"; exit $status'
WORKDIR /repo

# ---- Stage 2: runtime --------------------------------------------------------
FROM node:20-slim AS runner
WORKDIR /repo

ENV NODE_ENV=production
ENV PORT=3000

COPY --from=builder /repo /repo

EXPOSE 3000
WORKDIR /repo/apps/admin
# The Container App ingress targets port 3000; run Next on 3000 in the container.
CMD ["npx", "next", "start", "-p", "3000"]
