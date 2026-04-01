from app.domain.schemas import JobParsed
from app.persistence.db import Base
from app.persistence.repositories.jobs import JobsRepository
from app.services.dedup_service import DedupService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_dedup_prefers_linkedin_job_id():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    repo = JobsRepository(db)
    repo.create(
        gmail_message_id="msg-1",
        linkedin_job_id="123",
        linkedin_job_url="https://linkedin.com/comm/jobs/view/123/",
        status="new",
        seniority="nao_informado",
        work_model="nao_informado",
    )
    service = DedupService(db)
    parsed = JobParsed(gmail_message_id="msg-2", linkedin_job_id="123", linkedin_job_url="https://linkedin.com/comm/jobs/view/123/")
    assert service.is_duplicate(parsed) is True
