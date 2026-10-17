# Multi-stage build for React/Vite SPA
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Build-time safe validation: ensure VITE_API_URL does not point to localhost in production builds
RUN if [ -n "$VITE_API_URL" ] && echo "$VITE_API_URL" | grep -qiE "localhost|127\.0\.0\.1"; then \
      echo "FATAL: VITE_API_URL cannot point to localhost/127.0.0.1 in production deployment! Provided: $VITE_API_URL" && exit 1; \
    fi

RUN npm run build

# Post-build verification: verify no hardcoded localhost API endpoints were bundled into dist
RUN if grep -rq "http://localhost:" dist/ 2>/dev/null || grep -rq "http://127.0.0.1:" dist/ 2>/dev/null; then \
      echo "FATAL: Production bundle dist/ contains localhost API endpoints!" && exit 1; \
    fi


# Production static server stage with Caddy
FROM caddy:2-alpine

WORKDIR /srv

COPY --from=builder /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile

EXPOSE 80

CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
