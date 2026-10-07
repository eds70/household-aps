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
# Итоговый образ: ~50 MB (nginx-alpine + статика).

# ==========================================
# STAGE 1: BUILDER
# ==========================================
FROM node:20-alpine AS builder

WORKDIR /app

# ==========================================
# BUILD ARG: VITE_API_URL
# ==========================================
# Vite вшивает переменные окружения с префиксом VITE_* в бандл
# на этапе сборки. Это значит, что после сборки изменить API_URL
# без пересборки НЕЛЬЗЯ.
#
# Для локальной разработки — http://localhost:8000.
# Для облака — https://your-domain.com или http://<ip-сервера>.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}

# ==========================================
# УСТАНОВКА ЗАВИСИМОСТЕЙ (отдельный слой, кэшируется)
# ==========================================
# Копируем только манифесты — если код изменится,
# npm ci не переустанавливается.
COPY package.json package-lock.json ./

# npm ci — детерминированная установка по lock-файлу.
# --no-audit --no-fund — без интерактивных подсказок.
RUN npm ci --no-audit --no-fund

# ==========================================
# СБОРКА СТАТИКИ
# ==========================================
COPY . .

# npm run build = tsc -b && vite build
#   - tsc -b: строгая проверка типов (может упасть при TS-ошибке)
#   - vite build: сборка в dist/
# Результат: /app/dist/
RUN npm run build

# ==========================================
# STAGE 2: RUNTIME
# ==========================================
FROM nginx:alpine

# ==========================================
# МЕТАДАННЫЕ
# ==========================================
LABEL maintainer="APS Production Scheduler" \
      description="Frontend: React 19 + Vite, статика через nginx" \
      version="4.9.0"

# ==========================================
# ВНУТРЕННИЙ NGINX-КОНФИГ
# ==========================================
# Отдаёт SPA-статику с fallback на index.html
# (client-side routing — /audit, /help/:slug и т.д.).
COPY nginx.conf /etc/nginx/conf.d/default.conf

# ==========================================
# СТАТИКА ИЗ BUILDER
# ==========================================
COPY --from=builder /app/dist /usr/share/nginx/html

# ==========================================
# ПОРТ
# ==========================================
EXPOSE 80

# ==========================================
# HEALTHCHECK
# ==========================================
# wget уже есть в nginx:alpine.
# Проверяет, что nginx отвечает на / за 3 сек.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

# ==========================================
# CMD
# ==========================================
# Стандартная команда nginx:alpine.
CMD ["nginx", "-g", "daemon off;"]