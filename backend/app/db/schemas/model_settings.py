from app.db.schemas.common import CamelModel, UtcDateTime


class ModelSettingsOut(CamelModel):
    """Настройки модели (GET /model/settings): эффективные, дефолтные и время обновления"""

    settings: dict
    defaults: dict
    updated_at: UtcDateTime


class ModelSettingsPatchOut(ModelSettingsOut):
    """Ответ PATCH /model/settings: как GET плюс новая версия и время пересчёта"""

    version: int
    recalculated_at: UtcDateTime | None
