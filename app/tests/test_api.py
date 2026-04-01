from fastapi.testclient import TestClient

from app.main import app
from app.persistence.db import Base, engine, SessionLocal
from app.persistence.repositories.unknown_email_templates import UnknownEmailTemplateRepository

client = TestClient(app)


def setup_module(module):
    Base.metadata.create_all(bind=engine)


def test_health():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_jobs_requires_api_key():
    response = client.get("/api/v1/jobs")
    assert response.status_code in (401, 422)


def test_ignored_emails_endpoints_require_api_key():
    response = client.get("/api/v1/ignored-emails")
    assert response.status_code in (401, 422)


def test_ignored_emails_summary_and_listing_with_api_key():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        repo = UnknownEmailTemplateRepository(db)
        repo.create(
            run_id=999,
            gmail_message_id="msg-ignored-1",
            email_subject="Mensagem ignorada",
            email_from="LinkedIn <notifications-noreply@linkedin.com>",
            linkedin_template="email_member_message_v2",
            content_mode_used="text",
            parser_attempted="skipped_before_parse",
            sample_job_url=None,
            raw_email_link="https://mail.google.com/mail/u/0/#inbox/msg-ignored-1",
            reason="non_job_template",
        )
    finally:
        db.close()

    headers = {"X-API-Key": "change-me"}
    response = client.get("/api/v1/ignored-emails/by-reason", headers=headers)
    assert response.status_code == 200
    assert any(item["reason"] == "non_job_template" for item in response.json())

    response = client.get("/api/v1/ignored-emails?reason=non_job_template", headers=headers)
    assert response.status_code == 200
    assert any(item["gmail_message_id"] == "msg-ignored-1" for item in response.json())
