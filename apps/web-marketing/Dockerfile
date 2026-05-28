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

# Install workspace deps from root (npm sets up the @tyndale/shared symlink at
# apps/web-marketing/node_modules/@tyndale/shared → packages/shared/).
COPY package.json package-lock.json ./
COPY apps/web-marketing/package.json apps/web-marketing/
COPY packages/shared/package.json packages/shared/
RUN npm ci

# Copy source and build the marketing app (hybrid Next.js — SSR + API routes).
COPY packages/shared packages/shared
COPY apps/web-marketing apps/web-marketing
RUN npm --workspace=apps/web-marketing run build

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
