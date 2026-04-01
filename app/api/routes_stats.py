from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_api_key
from app.persistence.repositories.jobs import JobsRepository
from app.persistence.repositories.sync_runs import SyncRunRepository

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)) -> dict[str, int]:
    jobs_repo = JobsRepository(db)
    runs_repo = SyncRunRepository(db)
    return {
        "jobs_total": jobs_repo.count_all(),
        "jobs_parse_failed": jobs_repo.count_by_status("parse_failed"),
        "jobs_new": jobs_repo.count_by_status("new"),
        "runs_total": runs_repo.count_all(),
        "runs_failed": runs_repo.count_by_status("failed"),
    }
