from datetime import datetime, timezone

from app.domain.enums import JobStatus, Seniority, WorkModel
from app.persistence.db import Base, SessionLocal, engine
from app.persistence.repositories.jobs import JobsRepository


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        repo = JobsRepository(db)
        samples = [
            {
                "gmail_message_id": "seed-msg-001",
                "external_message_id": "<seed-001@example.com>",
                "linkedin_job_id": "4392930380",
                "linkedin_job_url": "https://linkedin.com/comm/jobs/view/4392930380/",
                "raw_email_link": "https://mail.google.com/mail/u/0/#inbox/seed-msg-001",
                "email_subject": "Novas vagas semelhantes para Backend Python",
                "linkedin_template": "email_jobs_viewed_job_reminder_01",
                "parser_used": "seed_demo_data",
                "title": "Desenvolvedor Python Pleno",
                "company": "Empresa Exemplo",
                "location_raw": "Campinas, SP",
                "seniority": Seniority.PLENO,
                "work_model": WorkModel.HIBRIDO,
                "received_at": datetime.now(timezone.utc),
                "body_html_hash": "seedhash001",
                "status": JobStatus.NEW,
                "raw_metadata_json": '{"source":"seed"}',
            },
            {
                "gmail_message_id": "seed-msg-001",
                "external_message_id": "<seed-001@example.com>",
                "linkedin_job_id": "4391875466",
                "linkedin_job_url": "https://linkedin.com/comm/jobs/view/4391875466/",
                "raw_email_link": "https://mail.google.com/mail/u/0/#inbox/seed-msg-001",
                "email_subject": "Novas vagas semelhantes para Backend Python",
                "linkedin_template": "email_jobs_viewed_job_reminder_01",
                "parser_used": "seed_demo_data",
                "title": "Desenvolvedor Python (Júnior) - Trabalho Remoto",
                "company": "BairesDev",
                "location_raw": "Brasil",
                "seniority": Seniority.JUNIOR,
                "work_model": WorkModel.REMOTO,
                "received_at": datetime.now(timezone.utc),
                "body_html_hash": "seedhash001",
                "status": JobStatus.NEW,
                "raw_metadata_json": '{"source":"seed"}',
            },
        ]
        inserted = 0
        for sample in samples:
            if sample["linkedin_job_id"] and repo.get_by_linkedin_job_id(sample["linkedin_job_id"]):
                continue
            repo.create(**sample)
            inserted += 1
        print(f"Seed concluido. Registros inseridos: {inserted}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
