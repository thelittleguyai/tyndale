# syntax=docker/dockerfile:1
#
# Next.js marketing landing for tyndale-dev-marketing Container App.
#
# Build context: REPO ROOT (not apps/web-marketing/) so the npm workspace
# packages (@tyndale/shared) resolve at install + build time.
#   docker build -f apps/web-marketing/Dockerfile -t IMAGE .
#
# This is the pattern the deploy-web-marketing.yml workflow uses.

# ---- Stage 1: build with workspace-aware npm install -------------------------
FROM node:20-slim AS builder
WORKDIR /repo

# Disable Next.js telemetry phone-home during build (no network needed).
ENV NEXT_TELEMETRY_DISABLED=1

# Build-time placeholder for AUTH_SECRET. Auth.js v5 evaluates NextAuth(config)
# at module load when route handlers are statically analyzed; in production
# mode it complains about a missing AUTH_SECRET. The *real* AUTH_SECRET comes
# from the Container App env at runtime — this value only exists to satisfy
# the build-time check and is never used to sign anything.
ENV AUTH_SECRET=build-only-placeholder-replaced-at-runtime-by-container-app-env

# Public runtime API base + app URL, baked into the client bundle at BUILD time.
# NEXT_PUBLIC_* are inlined by `next build`, so they MUST be present here — a
# Container App runtime env var is too late (the bundle is already built). The
# deploy workflow passes these via --build-arg; the defaults apply to local
# `docker build`. RUNTIME_URL is where the signin pages call /v1/auth/*.
ARG NEXT_PUBLIC_RUNTIME_URL=https://api.tyndaleapp.net
ARG NEXT_PUBLIC_APP_URL=https://app.tyndaleapp.net
ENV NEXT_PUBLIC_RUNTIME_URL=$NEXT_PUBLIC_RUNTIME_URL
ENV NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL

# Install workspace deps from root (npm hoists workspace symlinks to
# /repo/node_modules/@tyndale/shared → packages/shared/).
# tsconfig.base.json comes along now so the marketing tsconfig's
# `extends: "../../tsconfig.base.json"` resolves at build time (TS5083 if missing).
COPY package.json package-lock.json tsconfig.base.json ./
COPY apps/web-marketing/package.json apps/web-marketing/
COPY packages/shared/package.json packages/shared/
RUN npm ci

# Copy source and build the marketing app (hybrid Next.js — SSR + API routes).
COPY packages/shared packages/shared
COPY apps/web-marketing apps/web-marketing

# Belt-and-suspenders: ensure the Linux SWC binary is present even if the
# lockfile was generated on a non-Linux host and missed it (a known npm
# quirk with optional native deps). Harmless if already installed.
RUN npm install --no-save --include=optional @next/swc-linux-x64-gnu @next/swc-linux-x64-musl || true

# Pre-build diagnostics — visible in the docker buildx log regardless of
# whether the build later succeeds or fails. Cheap and chatty.
WORKDIR /repo/apps/web-marketing
RUN echo "==== node / npm ====" && node --version && npm --version \
 && echo "==== @tyndale/shared symlink ====" \
 && ls -la /repo/apps/web-marketing/node_modules/@tyndale/ 2>&1 || true \
 && echo "==== shared package.json ====" \
 && cat /repo/packages/shared/package.json \
 && echo "==== shared src files ====" \
 && ls -la /repo/packages/shared/src/ \
 && echo "==== next.config.mjs ====" \
 && cat next.config.mjs \
 && echo "==== marketing package.json ====" \
 && cat package.json \
 && echo "==== next info ====" \
 && (npx --yes next info 2>&1 | head -40 || true)

# Run next build directly so any error from the build script propagates with
# full stderr (npm --workspace can swallow output from the inner script).
# Force-flush stderr by piping through cat so buildkit captures the full tail.
RUN sh -c 'npm run build 2>&1; status=$?; echo "--- next build exit status: $status ---"; exit $status'
WORKDIR /repo

# ---- Stage 2: runtime --------------------------------------------------------
FROM node:20-slim AS runner
WORKDIR /repo

ENV NODE_ENV=production
ENV PORT=3000

# Carry the whole built workspace forward. Simpler than tracing standalone
# output across the monorepo; image is bigger (~400 MB) but predictable.
# Switch to Next.js standalone output if image size becomes a concern.
COPY --from=builder /repo /repo

EXPOSE 3000
WORKDIR /repo/apps/web-marketing
CMD ["npm", "run", "start"]
