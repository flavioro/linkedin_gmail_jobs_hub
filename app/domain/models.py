from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.db import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    gmail_message_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    linkedin_job_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, index=True)
    raw_email_link: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    email_subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    linkedin_template: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    parser_used: Mapped[str | None] = mapped_column(String(128), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seniority: Mapped[str] = mapped_column(String(32), default="nao_informado", nullable=False)
    work_model: Mapped[str] = mapped_column(String(32), default="nao_informado", nullable=False)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    body_html_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="new", nullable=False, index=True)
    raw_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_duplicates: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ParseFailure(Base):
    __tablename__ = "parse_failures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    gmail_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UnknownEmailTemplate(Base):
    __tablename__ = "unknown_email_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    gmail_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    email_subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    email_from: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_template: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    content_mode_used: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parser_attempted: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sample_job_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    raw_email_link: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SyncRunEvent(Base):
    __tablename__ = "sync_run_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProcessedGmailMessage(Base):
    __tablename__ = "processed_gmail_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    gmail_message_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    email_subject: Mapped[str | None] = mapped_column(String(512), nullable=True)
    linkedin_template: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False, default="processed")
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
