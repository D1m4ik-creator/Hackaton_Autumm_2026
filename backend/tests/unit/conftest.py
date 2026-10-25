import pytest


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    """Изолированные проверки файлов не используют PostgreSQL."""
    yield
