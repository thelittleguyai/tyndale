# syntax=docker/dockerfile:1
#
# Expo static web export for apps/mobile (the Tyndale product app), served by
# nginx at app.tyndaleapp.net.
#
# Build context: REPO ROOT (so the npm workspace package @tyndale/shared
# resolves at install/build time):
#   docker build -f apps/mobile/Dockerfile -t IMAGE .
# Mirrors the web-marketing Dockerfile's workspace-aware pattern.

# ---- Stage 1: static web export ---------------------------------------------
FROM node:20-slim AS builder
WORKDIR /repo
ENV EXPO_NO_TELEMETRY=1

# EXPO_PUBLIC_* values are INLINED into the JS bundle at export time, so the API
# base URL must be a build-arg — a Container App runtime env var is too late
# (the bundle is already built). The deploy workflow passes this; the default
# applies to a local `docker build`.
ARG EXPO_PUBLIC_API_BASE_URL=https://api.tyndaleapp.net
ENV EXPO_PUBLIC_API_BASE_URL=$EXPO_PUBLIC_API_BASE_URL

# Workspace-aware install from the repo root (hoists @tyndale/shared). The base
# tsconfig comes along so apps/mobile's `extends: ../../tsconfig.base.json`
# resolves at build time.
COPY package.json package-lock.json tsconfig.base.json ./
COPY apps/mobile/package.json apps/mobile/
COPY packages/shared/package.json packages/shared/
RUN npm ci

COPY packages/shared packages/shared
COPY apps/mobile apps/mobile

WORKDIR /repo/apps/mobile
# `expo export --platform web` -> static site in ./dist
RUN npm run export:web

# ---- Stage 2: nginx static server -------------------------------------------
FROM nginx:1.27-alpine AS runner
COPY apps/mobile/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /repo/apps/mobile/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
