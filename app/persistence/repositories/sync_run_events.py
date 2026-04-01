import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.models import SyncRunEvent


class SyncRunEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        run_id: int,
        level: str,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> SyncRunEvent:
        item = SyncRunEvent(
            run_id=run_id,
            level=level,
            event_type=event_type,
            message=message,
            payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def list_by_run_id(self, run_id: int) -> list[SyncRunEvent]:
        stmt = select(SyncRunEvent).where(SyncRunEvent.run_id == run_id).order_by(SyncRunEvent.id.asc())
        return list(self.db.execute(stmt).scalars().all())
