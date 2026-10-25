"""Настраивает локальный Authentik для входа в панель и пишет OIDC_* в backend/.env.

Что делает (повторный запуск безопасен — существующее обновляется, а не дублируется):
- Scope Mapping почты с email_verified=true (стандартный Authentik всегда отдаёт false,
  а бэкенд связывает аккаунты только по подтверждённой почте);
- OAuth2 Provider и Application «Aéza panel» (slug aeza-panel);
- OIDC_ENABLED/ISSUER/CLIENT_ID/CLIENT_SECRET/REDIRECT_URI/AUTHORIZE_URL, FRONTEND_URL,
  CORS_ORIGINS и AUTHENTIK_API_URL/TOKEN в backend/.env.

Нужно: запущенный Authentik (docker compose up -d authentik-db authentik-redis
authentik-server authentik-worker) и AUTHENTIK_BOOTSTRAP_TOKEN в backend/.env.
Запуск из каталога backend: python scripts/setup_authentik.py
Потом пересоздать api: docker compose up -d api

Секреты в вывод не печатаются. Адреса рассчитаны на фронт vite (127.0.0.1:5173)
и api в docker compose.
"""

import re
import sys
from pathlib import Path

import httpx

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
API_URL = "http://localhost:9000/api/v3"
SLUG = "aeza-panel"
NAME = "Aéza panel"
EMAIL_MAPPING_NAME = "Aéza: email (verified)"
REDIRECT_URI = "http://127.0.0.1:8000/api/v1/auth/oidc/callback"
FRONTEND_URL = "http://127.0.0.1:5173"
EMAIL_EXPRESSION = 'return {\n    "email": request.user.email,\n    "email_verified": True,\n}\n'


def read_env() -> dict[str, str]:
    return dict(re.findall(r"^([A-Z0-9_]+)=(.*)$", ENV_PATH.read_text(encoding="utf-8"), re.M))


def write_env(values: dict[str, str]) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    seen = set()
    for i, line in enumerate(lines):
        m = re.match(r"^([A-Z0-9_]+)=", line)
        if m and m.group(1) in values:
            lines[i] = f"{m.group(1)}={values[m.group(1)]}"
            seen.add(m.group(1))
    missing = [key for key in values if key not in seen]
    if missing:
        lines += ["", "# --- Вход через Authentik (scripts/setup_authentik.py) ---"]
        lines += [f"{key}={values[key]}" for key in missing]
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    env = read_env()
    token = env.get("AUTHENTIK_BOOTSTRAP_TOKEN", "").strip()
    if not token:
        sys.exit("В backend/.env нет AUTHENTIK_BOOTSTRAP_TOKEN — им скрипт ходит в API Authentik")
    client = httpx.Client(base_url=API_URL, headers={"Authorization": f"Bearer {token}"}, timeout=30)

    def first(path: str, **params) -> dict | None:
        results = client.get(path, params=params).raise_for_status().json()["results"]
        return results[0] if results else None

    def require(path: str, **params) -> dict:
        found = first(path, **params)
        if found is None:
            sys.exit(f"В Authentik не найдено {path} {params} — он ещё запускается? Повторите через минуту")
        return found

    email_body = {"name": EMAIL_MAPPING_NAME, "scope_name": "email", "expression": EMAIL_EXPRESSION,
                  "description": "Почта пользователя (подтверждена администратором)"}
    email_mapping = first("/propertymappings/provider/scope/", name=EMAIL_MAPPING_NAME)
    if email_mapping is None:
        email_mapping = client.post("/propertymappings/provider/scope/", json=email_body).raise_for_status().json()
    mappings = [
        require("/propertymappings/provider/scope/", managed=f"goauthentik.io/providers/oauth2/scope-{scope}")["pk"]
        for scope in ("openid", "profile")
    ] + [email_mapping["pk"]]

    provider_body = {
        "name": NAME,
        "authorization_flow": require("/flows/instances/", slug="default-provider-authorization-implicit-consent")["pk"],
        "invalidation_flow": require("/flows/instances/", slug="default-provider-invalidation-flow")["pk"],
        "client_type": "confidential",
        "redirect_uris": [{"matching_mode": "strict", "url": REDIRECT_URI}],
        "signing_key": require("/crypto/certificatekeypairs/", name="authentik Self-signed Certificate")["pk"],
        "property_mappings": mappings,
    }
    provider = first("/providers/oauth2/", name=NAME)
    if provider is None:
        provider = client.post("/providers/oauth2/", json=provider_body).raise_for_status().json()
    else:
        provider = client.patch(f"/providers/oauth2/{provider['pk']}/", json=provider_body).raise_for_status().json()

    if first("/core/applications/", slug=SLUG) is None:
        client.post("/core/applications/", json={"name": NAME, "slug": SLUG, "provider": provider["pk"]}).raise_for_status()

    cors = [origin for origin in env.get("CORS_ORIGINS", "").split(",") if origin]
    for origin in (FRONTEND_URL, "http://localhost:5173"):
        if origin not in cors:
            cors.append(origin)
    write_env({
        "OIDC_ENABLED": "true",
        # api ходит к Authentik по имени контейнера внутри сети compose
        "OIDC_ISSUER": f"http://authentik-server:9000/application/o/{SLUG}/",
        "OIDC_CLIENT_ID": provider["client_id"],
        "OIDC_CLIENT_SECRET": provider["client_secret"],
        "OIDC_REDIRECT_URI": REDIRECT_URI,
        "OIDC_AUTHORIZE_URL": "http://127.0.0.1:9000/application/o/authorize/",
        "FRONTEND_URL": FRONTEND_URL,
        "CORS_ORIGINS": ",".join(cors),
        "AUTHENTIK_API_URL": "http://authentik-server:9000",
        "AUTHENTIK_API_TOKEN": token,
    })
    print(f"Готово: Provider и Application «{NAME}» настроены, backend/.env обновлён.")
    print("Пересоздайте api, чтобы он подхватил новые OIDC_*: docker compose up -d api")


if __name__ == "__main__":
    main()
