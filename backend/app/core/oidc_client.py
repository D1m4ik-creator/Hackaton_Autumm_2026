from authlib.integrations.starlette_client import OAuth

from app.core.config import get_settings

OIDC_CLIENT_NAME = "authentik"

oauth = OAuth()


def register_oidc_client() -> None:
    """Регистрирует клиента authlib против Authentik; вызывать один раз при старте,
    только если OIDC_ENABLED=true — иначе запрос server_metadata_url на старте
    не отработает (провайдер может быть ещё не настроен или вообще не поднят).
    """
    settings = get_settings()
    oauth.register(
        OIDC_CLIENT_NAME,
        server_metadata_url=f"{settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration",
        # authorize_url в приоритете над authorization_endpoint из метаданных
        # (authlib: BaseApp.create_authorization_url — self.authorize_url or metadata[...])
        authorize_url=settings.oidc_authorize_url or None,
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret.get_secret_value(),
        client_kwargs={"scope": "openid profile email"},
    )
