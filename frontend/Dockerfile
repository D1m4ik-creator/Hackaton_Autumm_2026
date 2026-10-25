FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Адреса API и Grafana в образ не запекаются: nginx проксирует /api/, /metrics
# и /grafana/ на тот же origin (nginx.conf), фронт ходит на same-origin.
# VITE_API_URL/VITE_GRAFANA_URL используются только dev-сервером vite и тестами,
# в образ они попасть не должны.
RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
