# Prometheus + Grafana

Поднимаются вместе с остальным стеком: `docker compose up -d --build`.

## Адреса

- **Grafana**: http://localhost:3001 — логин `admin`, пароль из
  `GRAFANA_ADMIN_PASSWORD` в `backend/.env`.
- **Prometheus**: только `127.0.0.1:9090` (не публикуется в сеть) — для
  локальной отладки PromQL-запросов через UI (`/graph`) или `/targets`
  (проверить, что бэкенд в статусе UP).

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
