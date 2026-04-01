from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import JobStatus, Seniority, WorkModel


class JobParsed(BaseModel):
    gmail_message_id: str
    external_message_id: str | None = None
    linkedin_job_id: str | None = None
    linkedin_job_url: str | None = None
    raw_email_link: str | None = None
    email_subject: str | None = None
    linkedin_template: str | None = None
    parser_used: str | None = None
    title: str | None = None
    company: str | None = None
    location_raw: str | None = None
    is_easy_apply: bool | None = None
    seniority: Seniority = Seniority.NAO_INFORMADO
    work_model: WorkModel = WorkModel.NAO_INFORMADO
    received_at: datetime | None = None
    body_html_hash: str | None = None
    status: JobStatus = JobStatus.NEW
    raw_metadata_json: str | None = None


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    gmail_message_id: str
    external_message_id: str | None = None
    linkedin_job_id: str | None = None
    linkedin_job_url: str | None = None
    raw_email_link: str | None = None
    email_subject: str | None = None
    linkedin_template: str | None = None
    parser_used: str | None = None
    title: str | None = None
    company: str | None = None
    location_raw: str | None = None
    is_easy_apply: bool | None = None
    seniority: str
    work_model: str
    received_at: datetime | None = None
    body_html_hash: str | None = None
    status: str
    raw_metadata_json: str | None = None
    created_at: datetime
    updated_at: datetime




class IgnoredEmailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    gmail_message_id: str | None = None
    email_subject: str | None = None
    email_from: str | None = None
    linkedin_template: str | None = None
    content_mode_used: str | None = None
    parser_attempted: str | None = None
    sample_job_url: str | None = None
    raw_email_link: str | None = None
    reason: str
    created_at: datetime


class IgnoredEmailReasonSummary(BaseModel):
    reason: str
    total: int

class SyncRunQueuedResponse(BaseModel):
    run_id: int
    status: str = Field(default="queued")


class SyncRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_found: int
    total_processed: int
    total_inserted: int
    total_duplicates: int
    total_failed: int
    error_summary: str | None = None
    created_at: datetime


class SyncRunEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    level: str
    event_type: str
    message: str
    payload_json: str | None = None
    created_at: datetime
