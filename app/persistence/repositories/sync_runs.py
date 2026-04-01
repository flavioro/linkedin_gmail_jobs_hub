from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import SyncRun


class SyncRunRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_run(self, status: str) -> SyncRun:
        run = SyncRun(status=status)
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_by_id(self, run_id: int) -> SyncRun | None:
        return self.db.get(SyncRun, run_id)

    def list_runs(self) -> list[SyncRun]:
        stmt = select(SyncRun).order_by(SyncRun.id.desc())
        return list(self.db.execute(stmt).scalars().all())

    def count_all(self) -> int:
        return self.db.query(func.count(SyncRun.id)).scalar() or 0

    def count_by_status(self, status: str) -> int:
        return self.db.query(func.count(SyncRun.id)).filter(SyncRun.status == status).scalar() or 0

    def mark_running(self, run: SyncRun) -> SyncRun:
        run.status = "running"
        run.started_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(run)
        return run

    def mark_completed(self, run: SyncRun) -> SyncRun:
        run.status = "completed"
        run.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(run)
        return run

    def mark_failed(self, run: SyncRun, error_summary: str) -> SyncRun:
        merged = self.db.merge(run)
        merged.status = "failed"
        merged.error_summary = error_summary
        merged.finished_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(merged)
        return merged

    def save(self, run: SyncRun) -> SyncRun:
        merged = self.db.merge(run)
        self.db.commit()
        self.db.refresh(merged)
        return merged
