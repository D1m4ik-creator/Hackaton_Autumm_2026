from app.dao.base import BaseDAO
from app.db.models.share_link import ShareLink


class ShareLinkDAO(BaseDAO):
    model = ShareLink
