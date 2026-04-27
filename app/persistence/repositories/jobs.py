from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import Job


class JobsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> Job:
        job = Job(**kwargs)
        try:
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)
            return job
        except IntegrityError:
            self.db.rollback()
            raise

    def get_by_id(self, job_id: int) -> Job | None:
        return self.db.get(Job, job_id)

    def get_first_by_gmail_message_id(self, gmail_message_id: str) -> Job | None:
        stmt = select(Job).where(Job.gmail_message_id == gmail_message_id).order_by(Job.id.desc())
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_gmail_message_and_job_id(self, gmail_message_id: str, linkedin_job_id: str) -> Job | None:
        stmt = select(Job).where(Job.gmail_message_id == gmail_message_id, Job.linkedin_job_id == linkedin_job_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_gmail_message_and_url(self, gmail_message_id: str, linkedin_job_url: str) -> Job | None:
        stmt = select(Job).where(Job.gmail_message_id == gmail_message_id, Job.linkedin_job_url == linkedin_job_url)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_linkedin_job_id(self, linkedin_job_id: str) -> Job | None:
        stmt = select(Job).where(Job.linkedin_job_id == linkedin_job_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_normalized_url(self, linkedin_job_url: str) -> Job | None:
        stmt = select(Job).where(Job.linkedin_job_url == linkedin_job_url)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_jobs(
        self,
        company: str | None,
        seniority: str | None,
        work_model: str | None,
        is_easy_apply: bool | None,
        limit: int,
        offset: int,
    ) -> list[Job]:
        stmt = select(Job).order_by(Job.created_at.desc(), Job.id.desc()).limit(limit).offset(offset)
        if company:
            stmt = stmt.where(Job.company.ilike(f"%{company}%"))
        if seniority:
            stmt = stmt.where(Job.seniority == seniority)
        if work_model:
            stmt = stmt.where(Job.work_model == work_model)
        if is_easy_apply is not None:
            stmt = stmt.where(Job.is_easy_apply.is_(is_easy_apply))
        return list(self.db.execute(stmt).scalars().all())

    def list_recent_by_days(self, days: int) -> list[Job]:
        safe_days = max(int(days), 1)
        cutoff = datetime.now(timezone.utc) - timedelta(days=safe_days)
        stmt = (
            select(Job)
            .where(func.coalesce(Job.received_at, Job.created_at) >= cutoff)
            .order_by(func.coalesce(Job.received_at, Job.created_at).desc(), Job.id.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_all(self) -> int:
        return self.db.query(func.count(Job.id)).scalar() or 0

    def count_by_status(self, status: str) -> int:
        return self.db.query(func.count(Job.id)).filter(Job.status == status).scalar() or 0
