from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_api_key
from app.domain.schemas import SyncRunEventRead, SyncRunRead, SyncRunQueuedResponse
from app.persistence.repositories.sync_run_events import SyncRunEventRepository
from app.persistence.repositories.sync_runs import SyncRunRepository
from app.services.sync_service import SyncService

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post("", response_model=SyncRunQueuedResponse, status_code=status.HTTP_202_ACCEPTED)
def start_sync(background_tasks: BackgroundTasks, db: Session = Depends(get_db)) -> SyncRunQueuedResponse:
    repo = SyncRunRepository(db)
    run = repo.create_run(status="queued")
    background_tasks.add_task(SyncService().run_sync, run.id)
    return SyncRunQueuedResponse(run_id=run.id, status=run.status)


@router.get("/runs", response_model=list[SyncRunRead])
def list_runs(db: Session = Depends(get_db)) -> list[SyncRunRead]:
    repo = SyncRunRepository(db)
    return [SyncRunRead.model_validate(run) for run in repo.list_runs()]


@router.get("/runs/{run_id}", response_model=SyncRunRead)
def get_run(run_id: int, db: Session = Depends(get_db)) -> SyncRunRead:
    repo = SyncRunRepository(db)
    run = repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    return SyncRunRead.model_validate(run)


@router.get("/runs/{run_id}/events", response_model=list[SyncRunEventRead])
def list_run_events(run_id: int, db: Session = Depends(get_db)) -> list[SyncRunEventRead]:
    runs_repo = SyncRunRepository(db)
    run = runs_repo.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found.")
    repo = SyncRunEventRepository(db)
    return [SyncRunEventRead.model_validate(event) for event in repo.list_by_run_id(run_id)]
