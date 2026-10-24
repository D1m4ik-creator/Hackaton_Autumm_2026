"""Интеграционные тесты SessionsDAO против реального PostgreSQL (docker-compose)."""

import uuid
from datetime import datetime, timedelta, timezone

from app.core.security import hash_token
from app.dao.session import SessionsDAO


def _session_values(**overrides):
    values = {
        "id": uuid.uuid4(),
        "login": "admin",
        "refresh_token_hash": hash_token("token"),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
    }
    values.update(overrides)
    return values


async def test_add_and_find_by_id(db_session):
    created = await SessionsDAO.add(db_session, **_session_values())

    found = await SessionsDAO.find_by_id(db_session, created.id)
    assert found is not None
    assert found.login == "admin"
    assert found.created_at is not None  # server_default сработал


async def test_find_one_or_none(db_session):
    created = await SessionsDAO.add(db_session, **_session_values())

    found = await SessionsDAO.find_one_or_none(db_session, login="admin")
    assert found is not None and found.id == created.id
    assert await SessionsDAO.find_one_or_none(db_session, login="nobody") is None


async def test_find_all_with_filter(db_session):
    await SessionsDAO.add(db_session, **_session_values(login="admin"))
    await SessionsDAO.add(db_session, **_session_values(login="other"))

    all_rows = await SessionsDAO.find_all(db_session)
    only_admin = await SessionsDAO.find_all(db_session, login="admin")

    assert len(all_rows) == 2
    assert len(only_admin) == 1 and only_admin[0].login == "admin"


async def test_rotate_refresh_hash_success(db_session):
    created = await SessionsDAO.add(db_session, **_session_values())
    old_hash = created.refresh_token_hash
    new_hash = hash_token("new-token")

    rotated = await SessionsDAO.rotate_refresh_hash(db_session, created.id, old_hash, new_hash)
    assert rotated is True
    created_id = created.id

    # rotate_refresh_hash работает с synchronize_session=False: объект в identity map
    # устарел, сбрасываем кэш сессии, чтобы прочитать актуальные значения из БД
    db_session.expire_all()
    updated = await SessionsDAO.find_by_id(db_session, created_id)
    assert updated.refresh_token_hash == new_hash
    assert updated.previous_token_hash == old_hash
    assert updated.rotated_at is not None


async def test_rotate_refresh_hash_rejects_stale_hash(db_session):
    """Повторная замена с тем же старым хэшем не проходит — токен уже заменён."""
    created = await SessionsDAO.add(db_session, **_session_values())
    old_hash = created.refresh_token_hash

    assert await SessionsDAO.rotate_refresh_hash(db_session, created.id, old_hash, hash_token("t2")) is True
    assert await SessionsDAO.rotate_refresh_hash(db_session, created.id, old_hash, hash_token("t3")) is False


async def test_delete_expired(db_session):
    now = datetime.now(timezone.utc)
    alive = await SessionsDAO.add(db_session, **_session_values(expires_at=now + timedelta(days=1)))
    await SessionsDAO.add(db_session, **_session_values(expires_at=now - timedelta(days=1)))

    await SessionsDAO.delete_expired(db_session)

    remaining = await SessionsDAO.find_all(db_session)
    assert [row.id for row in remaining] == [alive.id]


async def test_delete_by_id(db_session):
    created = await SessionsDAO.add(db_session, **_session_values())

    await SessionsDAO.delete_by_id(db_session, created.id)

    assert await SessionsDAO.find_by_id(db_session, created.id) is None
