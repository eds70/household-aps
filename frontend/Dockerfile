# frontend/Dockerfile
#
# Multi-stage сборка:
#   Stage 1 (builder) — Node 20: установка зависимостей + сборка статики.
#   Stage 2 (runtime) — nginx:alpine: отдаёт готовый dist.
#
# Сборка (из корня проекта):
#   docker build \
#     --build-arg VITE_API_URL=https://your-domain.com \
#     -t aps-frontend \
#     -f frontend/Dockerfile frontend/
#
# Через docker-compose.prod.yml:
#   docker compose -f docker-compose.prod.yml build frontend
#
# ОПТИМИЗАЦИЯ (2026-10-11):
#   - BuildKit cache mount для npm-кэша (~500 MB): не качается заново
#   - BuildKit cache mount для Vite-кэша (.vite): быстрее повторная сборка
#   - Второй build: npm ci за 5-10 сек вместо 1-3 мин
#
# Итоговый образ: ~50 MB (nginx-alpine + статика).

# syntax=docker/dockerfile:1.6

# ==========================================
# STAGE 1: BUILDER
# ==========================================
FROM node:20-alpine AS builder

WORKDIR /app

# ==========================================
# BUILD ARG: VITE_API_URL
# ==========================================
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}

# Используем /root/.npm как npm-кэш. При cache mount он переживёт
# пересборку, и npm не будет качать пакеты заново.
ENV NPM_CONFIG_CACHE=/root/.npm

# ==========================================
# УСТАНОВКА ЗАВИСИМОСТЕЙ (отдельный слой, кэшируется)
# ==========================================
COPY package.json package-lock.json ./

# --mount=type=cache,target=/root/.npm — npm-кэш переживает пересборку.
# Второй раз npm ci займёт 5-10 сек вместо 1-3 минут.
# --prefer-offline — использовать кэш где возможно.
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund --prefer-offline

# ==========================================
# СБОРКА СТАТИКИ
# ==========================================
COPY . .

# --mount=type=cache,target=/app/node_modules/.vite — кэш Vite
# переживает пересборку. Повторный npm run build быстрее.
RUN --mount=type=cache,target=/app/node_modules/.vite \
    npm run build

# ==========================================
# STAGE 2: RUNTIME
# ==========================================
FROM nginx:alpine

LABEL maintainer="APS Production Scheduler" \
      description="Frontend: React 19 + Vite, статика через nginx" \
      version="4.9.1"

# Внутренний nginx-конфиг (SPA-роутинг с fallback на index.html)
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Статика из builder
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]