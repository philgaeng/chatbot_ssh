# GRM Ticketing UI — Next.js 16 production image
# Multi-stage: build → standalone runtime

# ── Stage 1: deps ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# ── Stage 2: builder ───────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Build args injected at build time (NEXT_PUBLIC_* are inlined by the compiler)
# Note: TICKETING_API_URL is a runtime env var (not NEXT_PUBLIC_), set via
# Docker Compose 'environment' — no need to bake it into the image.
ARG NEXT_PUBLIC_BYPASS_AUTH=false
ARG NEXT_PUBLIC_OIDC_ISSUER=
ARG NEXT_PUBLIC_OIDC_CLIENT_ID=ticketing-ui
ARG NEXT_PUBLIC_REDIRECT_SIGN_IN=
ARG NEXT_PUBLIC_REDIRECT_SIGN_OUT=

ENV NEXT_PUBLIC_BYPASS_AUTH=$NEXT_PUBLIC_BYPASS_AUTH
ENV NEXT_PUBLIC_OIDC_ISSUER=$NEXT_PUBLIC_OIDC_ISSUER
ENV NEXT_PUBLIC_OIDC_CLIENT_ID=$NEXT_PUBLIC_OIDC_CLIENT_ID
ENV NEXT_PUBLIC_REDIRECT_SIGN_IN=$NEXT_PUBLIC_REDIRECT_SIGN_IN
ENV NEXT_PUBLIC_REDIRECT_SIGN_OUT=$NEXT_PUBLIC_REDIRECT_SIGN_OUT

# Enable Next.js standalone output
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── Stage 3: runner ────────────────────────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser  --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3001
ENV PORT=3001
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
