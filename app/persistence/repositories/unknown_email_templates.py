from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import UnknownEmailTemplate


class UnknownEmailTemplateRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> UnknownEmailTemplate:
        item = UnknownEmailTemplate(**kwargs)
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def list_items(self, *, reason: str | None = None, limit: int = 100, offset: int = 0) -> list[UnknownEmailTemplate]:
        stmt = select(UnknownEmailTemplate)
        if reason:
            stmt = stmt.where(UnknownEmailTemplate.reason == reason)
        stmt = stmt.order_by(UnknownEmailTemplate.id.desc()).offset(offset).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_by_reason(self) -> list[dict[str, int | str]]:
        stmt = (
            select(UnknownEmailTemplate.reason, func.count(UnknownEmailTemplate.id).label("total"))
            .group_by(UnknownEmailTemplate.reason)
            .order_by(func.count(UnknownEmailTemplate.id).desc(), UnknownEmailTemplate.reason.asc())
        )
        rows = self.db.execute(stmt).all()
        return [{"reason": row[0], "total": row[1]} for row in rows]
