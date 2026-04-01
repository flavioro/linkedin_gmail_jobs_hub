from sqlalchemy.orm import Session

from app.domain.schemas import JobParsed
from app.persistence.repositories.jobs import JobsRepository


class DedupService:
    def __init__(self, db: Session) -> None:
        self.repo = JobsRepository(db)

    def is_duplicate(self, job: JobParsed) -> bool:
        if job.linkedin_job_id:
            if self.repo.get_by_linkedin_job_id(job.linkedin_job_id):
                return True
            if self.repo.get_by_gmail_message_and_job_id(job.gmail_message_id, job.linkedin_job_id):
                return True
        if job.linkedin_job_url:
            if self.repo.get_by_normalized_url(job.linkedin_job_url):
                return True
            if self.repo.get_by_gmail_message_and_url(job.gmail_message_id, job.linkedin_job_url):
                return True
        return False
