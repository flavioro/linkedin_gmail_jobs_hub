from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.persistence.repositories.jobs import JobsRepository


@dataclass
class JobCsvExportResult:
    output_path: Path
    days: int
    row_count: int


class JobCsvExportService:
    FIELDNAMES = [
        "id",
        "gmail_message_id",
        "external_message_id",
        "linkedin_job_id",
        "linkedin_job_url",
        "raw_email_link",
        "email_subject",
        "linkedin_template",
        "parser_used",
        "title",
        "company",
        "location_raw",
        "is_easy_apply",
        "seniority",
        "work_model",
        "received_at",
        "body_html_hash",
        "status",
        "raw_metadata_json",
        "created_at",
        "updated_at",
    ]

    def export_recent_jobs(self, db: Session, days: int | None = None) -> JobCsvExportResult:
        effective_days = max(int(days or settings.gmail_newer_than_days), 1)
        jobs = JobsRepository(db).list_recent_by_days(effective_days)

        export_dir = Path(settings.csv_export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)
        output_path = export_dir / f"jobs_last_{effective_days}_days.csv"

        with output_path.open("w", newline="", encoding="utf-8-sig") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.FIELDNAMES)
            writer.writeheader()
            for job in jobs:
                writer.writerow(
                    {
                        "id": job.id,
                        "gmail_message_id": job.gmail_message_id,
                        "external_message_id": job.external_message_id,
                        "linkedin_job_id": job.linkedin_job_id,
                        "linkedin_job_url": job.linkedin_job_url,
                        "raw_email_link": job.raw_email_link,
                        "email_subject": job.email_subject,
                        "linkedin_template": job.linkedin_template,
                        "parser_used": job.parser_used,
                        "title": job.title,
                        "company": job.company,
                        "location_raw": job.location_raw,
                        "is_easy_apply": job.is_easy_apply,
                        "seniority": job.seniority,
                        "work_model": job.work_model,
                        "received_at": job.received_at.isoformat() if job.received_at else "",
                        "body_html_hash": job.body_html_hash,
                        "status": job.status,
                        "raw_metadata_json": job.raw_metadata_json,
                        "created_at": job.created_at.isoformat() if job.created_at else "",
                        "updated_at": job.updated_at.isoformat() if job.updated_at else "",
                    }
                )

        return JobCsvExportResult(
            output_path=output_path,
            days=effective_days,
            row_count=len(jobs),
        )
