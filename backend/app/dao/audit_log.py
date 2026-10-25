from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dao.base import BaseDAO
from app.db.models.audit import AuditLog


class AuditLogDAO(BaseDAO):
    model = AuditLog

    @classmethod
    async def list_page(cls, session: AsyncSession, *, page: int, page_size: int) -> Sequence[AuditLog]:
        """Страница записей аудита, новые сверху"""
        result = await session.execute(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        return result.scalars().all()
