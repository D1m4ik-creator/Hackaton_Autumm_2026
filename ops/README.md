# Prometheus + Grafana

Поднимаются вместе с остальным стеком: `docker compose up -d --build`.

## Адреса

- **Локально**: <http://localhost:3001> — логин `admin`, пароль из
  `GF_SECURITY_ADMIN_PASSWORD` в `backend/.env`.
- **На сервере**: `https://<домен>/grafana/` — nginx проксирует подпуть на сервис
  `grafana` (frontend/nginx.conf), порты 3001/9090 наружу не публикуются
  (только 127.0.0.1). Для этого в `backend/.env` на сервере должны быть
  `GF_SERVER_ROOT_URL=https://<домен>/grafana/` и `GF_SERVER_SERVE_FROM_SUB_PATH=true`
  (см. backend/.env.example). Снаружи подпуть закрыт сессией панели: nginx
  проверяет cookie через `GET /api/v1/auth/me` (auth_request), поэтому
  анонимный Viewer Grafana работает только для залогиненных в панель.
- **Prometheus**: только `127.0.0.1:9090` (не публикуется в сеть) — для
  локальной отладки PromQL-запросов через UI (`/graph`) или `/targets`
  (проверить, что бэкенд в статусе UP).

## Встраивание в панель

Дашборд «Churn Overview» также открывается прямо внутри панели — пункт
«Графики (Grafana)» в сайдбаре (`frontend/src/pages/grafana`). Технически
это iframe на `GF_SECURITY_ALLOW_EMBEDDING=true` + `kiosk`-режим (прячет
собственные шапку/меню Grafana). Внутри фрейма работает анонимный доступ
(`GF_AUTH_ANONYMOUS_*`, роль Viewer) — на `http://localhost` без HTTPS
сессионная cookie Grafana не доходит до iframe на другом порту (SameSite),
поэтому логин внутри фрейма не используется. Прямой вход на localhost:3001
(редактирование дашбордов/алертов) по-прежнему требует пароль админа.

## Дашборд

«Churn Overview» (папка по умолчанию) — провижинится автоматически из
`ops/grafana/dashboards/churn-overview.json`:

- Клиенты по уровню риска во времени.
- Ожидаемые потери в евро во времени.
- Свежесть данных (минут с последнего пересчёта).
- Счётчик пересчётов.

## Алерты

Папка «Churn Alerts» (Grafana Alerting, провижинится из
`ops/grafana/provisioning/alerting/rules.yml`), три правила:

1. Клиентов с высоким риском больше 5.
2. Ожидаемые потери выросли больше чем на 20% за 24 часа.
3. Пересчёта не было больше 6 часов (данные протухли).

Пороги захардкожены в YAML — под реальный бизнес их нужно подбирать
отдельно. **Доставка уведомлений не настроена** (нет SMTP/webhook) — алерты
видно только в самой Grafana (Alerting → Alert rules, статус Firing/Normal).
Чтобы получать реальные уведомления, нужно добавить contact point (Slack,
email, webhook) в Grafana UI или новым provisioning-файлом в
`ops/grafana/provisioning/alerting/`.

Правило #2 первые 24 часа после первого запуска будет в состоянии `NoData`
(`offset 24h` ещё не на что ссылаться) — это ожидаемо, не баг.
