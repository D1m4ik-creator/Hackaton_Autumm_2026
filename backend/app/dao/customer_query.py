from collections.abc import Sequence

from sqlalchemy import Row, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.account import Account
from app.db.models.risk_result import RiskResult
from app.db.models.service import Service
from app.db.models.transaction import Transaction

# Белый список колонок сортировки: ключ из API -> колонка таблицы
SORT_COLUMNS = {
    "id": Account.id,
    "email": Account.email,
    "balance": Account.balance,
    "totalReplenished": Account.total_replenished,
    "riskScore": RiskResult.score,
    "expectedLossCents": RiskResult.expected_loss_cents,
}

# Нет строки в risk_results -> клиент считается без оценки
_level_expr = func.coalesce(RiskResult.level, "no_data")


BIGINT_MAX = 2**63 - 1


def _escape_like(value: str) -> str:
    """Экранирует спецсимволы LIKE, чтобы подстрока искалась буквально"""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _conditions(levels: Sequence[str] | None, search: str | None) -> list:
    """Условия WHERE, общие для списка и для count"""
    conds: list = []
    if levels:
        conds.append(_level_expr.in_(list(levels)))
    if search and search.strip():
        # NUL недопустим в тексте Postgres — убираем, чтобы ilike не падал
        term = search.strip().replace("\x00", "")
        email_cond = Account.email.ilike(f"%{_escape_like(term)}%", escape="\\")
        # Только ASCII-цифры в пределах BIGINT -> дополнительно точное совпадение по id
        if term.isascii() and term.isdigit() and int(term) <= BIGINT_MAX:
            conds.append(or_(email_cond, Account.id == int(term)))
        else:
            conds.append(email_cond)
    return conds


async def query_customers(
    session: AsyncSession,
    *,
    levels: Sequence[str] | None,
    search: str | None,
    sort: str,
    order: str,
    page: int,
    page_size: int,
) -> Sequence[Row]:
    """Страница клиентов: accounts LEFT JOIN risk_results, сортировка из белого списка, NULLS LAST"""
    sort_col = SORT_COLUMNS.get(sort, RiskResult.score)
    direction = sort_col.desc() if order == "desc" else sort_col.asc()
    stmt = (
        select(
            Account.id,
            Account.email,
            Account.balance,
            Account.total_replenished,
            RiskResult.score,
            _level_expr.label("level"),
            func.coalesce(RiskResult.expected_loss_cents, 0).label("expected_loss_cents"),
            func.coalesce(RiskResult.reason_short, "").label("reason_short"),
        )
        .select_from(Account)
        .outerjoin(RiskResult, RiskResult.account_id == Account.id)
        .where(*_conditions(levels, search))
        .order_by(direction.nulls_last(), Account.id.asc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    result = await session.execute(stmt)
    return result.all()


async def count_customers(
    session: AsyncSession, *, levels: Sequence[str] | None, search: str | None
) -> int:
    """Число клиентов с тем же фильтром, что и список"""
    stmt = (
        select(func.count())
        .select_from(Account)
        .outerjoin(RiskResult, RiskResult.account_id == Account.id)
        .where(*_conditions(levels, search))
    )
    result = await session.execute(stmt)
    return result.scalar_one()


async def customer_services(session: AsyncSession, account_id: int) -> Sequence[Service]:
    """Услуги клиента, отсортированные по id (для карточки)"""
    result = await session.execute(
        select(Service).where(Service.owner_id == account_id).order_by(Service.id)
    )
    return result.scalars().all()


async def customer_transaction_counts(session: AsyncSession, account_id: int) -> dict:
    """Счётчики транзакций клиента по статусам: total / performed / not_performed"""
    result = await session.execute(
        select(Transaction.status, func.count())
        .select_from(Transaction)
        .join(Service, Service.id == Transaction.service_id)
        .where(Service.owner_id == account_id)
        .group_by(Transaction.status)
    )
    counts = {status: n for status, n in result.all()}
    performed = counts.get("performed", 0)
    not_performed = counts.get("not_performed", 0)
    return {"total": performed + not_performed, "performed": performed, "not_performed": not_performed}
