from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_api_key
from app.domain.schemas import JobRead
from app.persistence.repositories.jobs import JobsRepository

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("", response_model=list[JobRead])
def list_jobs(
    db: Session = Depends(get_db),
    company: str | None = None,
    seniority: str | None = None,
    work_model: str | None = None,
    is_easy_apply: Annotated[bool | None, Query(description="Filter by LinkedIn Easy Apply / Candidatura simplificada when known.")] = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[JobRead]:
    repo = JobsRepository(db)
    jobs = repo.list_jobs(
        company=company,
        seniority=seniority,
        work_model=work_model,
        is_easy_apply=is_easy_apply,
        limit=limit,
        offset=offset,
    )
    return [JobRead.model_validate(job) for job in jobs]


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobRead:
    repo = JobsRepository(db)
    job = repo.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return JobRead.model_validate(job)
