# syntax=docker/dockerfile:1
#
# Wrapper HTTP service for the tyndale-dev-wrapper Container App.
#
# Unlike the apps/* images, api-wrapper is a STANDALONE package (its own
# package-lock, not an npm workspace), so the build context is this directory:
#   docker build -f api-wrapper/Dockerfile -t IMAGE api-wrapper
#
# It has no runtime npm dependencies — the compiled output imports only Node
# built-ins — so the runtime stage ships just package.json (for "type":"module")
# and the compiled dist. tsc/tsx/@types are build-only and never shipped.

# ---- Stage 1: build ----------------------------------------------------------
FROM node:20-slim AS builder
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# ---- Stage 2: runtime --------------------------------------------------------
FROM node:20-slim AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=8088

COPY package.json ./
COPY --from=builder /app/dist ./dist

USER node
EXPOSE 8088
CMD ["node", "dist/server.js"]
