FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Адрес API в образ не запекается: nginx проксирует /api/ и /metrics на тот же
# origin (nginx.conf), фронт ходит на same-origin. VITE_API_URL используется
# только dev-сервером vite и тестами, в образ он попасть не должен.
RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
