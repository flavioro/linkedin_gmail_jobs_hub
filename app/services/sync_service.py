from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.infra.gmail_client import GmailClient
from app.persistence.db import SessionLocal
from app.persistence.repositories.jobs import JobsRepository
from app.persistence.repositories.parse_failures import ParseFailureRepository
from app.persistence.repositories.processed_gmail_messages import ProcessedGmailMessageRepository
from app.persistence.repositories.sync_run_events import SyncRunEventRepository
from app.persistence.repositories.sync_runs import SyncRunRepository
from app.persistence.repositories.unknown_email_templates import UnknownEmailTemplateRepository
from app.services.dedup_service import DedupService
from app.services.error_service import ErrorService
from app.services.parse_service import ParseService
from app.services.retry_service import RetryService

logger = logging.getLogger(__name__)


class SyncService:
    JOB_TEMPLATES = {
        "email_jobs_viewed_job_reminder_01",
        "email_jobs_saved_job_reminder_01",
        "email_application_confirmation_with_nba_01",
        "email_job_alert_digest_01",
    }
    NON_JOB_TEMPLATES = {
        "email_pymk_02",
        "email_m2m_invite_single_01",
        "email_member_message_v2",
        "email_groups_recommended_by_admin_01",
        "email_weekly_analytics_recap_v2",
    }

    def __init__(self) -> None:
        self.gmail_client = GmailClient()
        self.parse_service = ParseService()
        self.error_service = ErrorService()
        self.retry_service = RetryService(
            max_attempts=settings.retry_max_attempts,
            base_delay_seconds=settings.retry_base_delay_seconds,
            jitter_seconds=settings.retry_jitter_seconds,
        )

    def run_sync(self, run_id: int) -> None:
        db: Session = SessionLocal()
        run_repo = SyncRunRepository(db)
        jobs_repo = JobsRepository(db)
        failure_repo = ParseFailureRepository(db)
        processed_repo = ProcessedGmailMessageRepository(db)
        unknown_repo = UnknownEmailTemplateRepository(db)
        events_repo = SyncRunEventRepository(db)
        dedup_service = DedupService(db)
        run = run_repo.get_by_id(run_id)
        if not run:
            db.close()
            return

        try:
            run = run_repo.mark_running(run)
            self._event(events_repo, run_id, "info", "sync_started", "Gmail sync started", {"run_id": run_id})
            if not settings.enable_gmail_sync:
                run_repo.mark_failed(run, "sync_disabled")
                self._event(events_repo, run_id, "warning", "sync_disabled", "Gmail sync disabled by configuration")
                return

            auth_status = self.gmail_client.check_auth_status(interactive=False)
            if not auth_status.ok:
                logger.error(
                    "gmail auth preflight failed | run_id=%s | code=%s | message=%s",
                    run_id,
                    auth_status.code,
                    auth_status.message,
                )
                self._event(
                    events_repo,
                    run_id,
                    "error",
                    "gmail_auth_failed",
                    "Falha na validacao da autenticacao do Gmail antes da sincronizacao",
                    {
                        "code": auth_status.code,
                        "detail": auth_status.message,
                        "token_file": str(self.gmail_client.token_file),
                        "credentials_file": str(self.gmail_client.credentials_file),
                    },
                )
                run_repo.mark_failed(run, auth_status.code)
                return

            effective_query, raw_message_ids = self._find_message_ids(events_repo, run_id)
            logger.info("starting gmail sync | run_id=%s | query=%s", run_id, effective_query)
            self._event(events_repo, run_id, "info", "query_built", "Gmail query built", {"query": effective_query})

            already_processed_ids = processed_repo.list_existing_ids(raw_message_ids)
            message_ids = [message_id for message_id in raw_message_ids if message_id not in already_processed_ids]

            run.total_found = len(message_ids)
            run = run_repo.save(run)
            logger.info(
                "gmail sync messages found | run_id=%s | raw_total_found=%s | new_total_found=%s | skipped_processed=%s",
                run_id,
                len(raw_message_ids),
                run.total_found,
                len(already_processed_ids),
            )
            self._event(
                events_repo,
                run_id,
                "info",
                "gmail_messages_found",
                "Gmail messages found",
                {
                    "raw_total_found": len(raw_message_ids),
                    "new_total_found": run.total_found,
                    "skipped_processed": len(already_processed_ids),
                    "query": effective_query,
                },
            )

            if not message_ids:
                logger.info("gmail sync completed with no new matching messages | run_id=%s", run_id)
                self._event(
                    events_repo,
                    run_id,
                    "info",
                    "sync_completed_no_messages",
                    "No new Gmail messages matched the configured query",
                    {"query": effective_query, "skipped_processed": len(already_processed_ids)},
                )
                run_repo.mark_completed(run)
                return

            for message_id in message_ids:
                subject = None
                linkedin_template = None
                try:
                    message = self.retry_service.run(
                        lambda message_id=message_id: self.gmail_client.get_message(message_id),
                        should_retry=self.error_service.is_transient,
                        on_retry=lambda attempt, exc, delay, message_id=message_id: self._handle_retry(
                            events_repo,
                            run_id,
                            "get_message",
                            attempt,
                            exc,
                            delay,
                            {"gmail_message_id": message_id},
                        ),
                    )
                    bodies = self.gmail_client.extract_bodies(message)
                    headers = self.gmail_client.extract_headers(message)
                    subject = headers.get("Subject")
                    linkedin_template = headers.get("X-LinkedIn-Template")
                    sender = headers.get("From")
                    logger.info(
                        "processing gmail message | run_id=%s | gmail_message_id=%s | subject=%r | template=%r",
                        run_id,
                        message_id,
                        subject,
                        linkedin_template,
                    )
                    self._event(
                        events_repo,
                        run_id,
                        "info",
                        "message_processing_started",
                        "Processing Gmail message",
                        {
                            "gmail_message_id": message_id,
                            "subject": subject,
                            "template": linkedin_template,
                        },
                    )

                    should_process, ignore_reason = self._should_process_message(headers, bodies)
                    if not should_process:
                        unknown_repo.create(
                            run_id=run_id,
                            gmail_message_id=message_id,
                            email_subject=subject,
                            email_from=sender,
                            linkedin_template=linkedin_template,
                            content_mode_used="plain_text" if bodies.get("text") else "html",
                            parser_attempted="skipped_before_parse",
                            sample_job_url=self._find_first_job_link((bodies.get("text") or "") + "\n" + (bodies.get("html") or "")),
                            raw_email_link=f"https://mail.google.com/mail/u/0/#inbox/{message_id}",
                            reason=ignore_reason,
                        )
                        processed_repo.create_or_ignore(
                            gmail_message_id=message_id,
                            run_id=run_id,
                            email_subject=subject,
                            linkedin_template=linkedin_template,
                            outcome=ignore_reason,
                        )
                        logger.info(
                            "gmail message ignored | run_id=%s | gmail_message_id=%s | subject=%r | template=%r | reason=%s",
                            run_id,
                            message_id,
                            subject,
                            linkedin_template,
                            ignore_reason,
                        )
                        self._event(
                            events_repo,
                            run_id,
                            "info",
                            "message_ignored",
                            "Gmail message ignored before parse",
                            {
                                "gmail_message_id": message_id,
                                "subject": subject,
                                "template": linkedin_template,
                                "reason": ignore_reason,
                            },
                        )
                        continue

                    if linkedin_template and linkedin_template not in self.JOB_TEMPLATES:
                        unknown_repo.create(
                            run_id=run_id,
                            gmail_message_id=message_id,
                            email_subject=subject,
                            email_from=sender,
                            linkedin_template=linkedin_template,
                            content_mode_used="plain_text" if bodies.get("text") else "html",
                            parser_attempted="fallback_dispatch",
                            sample_job_url=self._find_first_job_link((bodies.get("text") or "") + "\n" + (bodies.get("html") or "")),
                            raw_email_link=f"https://mail.google.com/mail/u/0/#inbox/{message_id}",
                            reason="template_not_mapped",
                        )
                        logger.warning(
                            "unknown linkedin template detected | run_id=%s | gmail_message_id=%s | subject=%r | template=%r",
                            run_id,
                            message_id,
                            subject,
                            linkedin_template,
                        )
                        self._event(
                            events_repo,
                            run_id,
                            "warning",
                            "template_unknown",
                            "Unknown LinkedIn template detected",
                            {
                                "gmail_message_id": message_id,
                                "subject": subject,
                                "template": linkedin_template,
                            },
                        )

                    parsed_jobs = self.parse_service.parse_many(
                        gmail_message_id=message_id,
                        headers=headers,
                        html=bodies["html"],
                        text=bodies["text"],
                    )

                    parsed_jobs = [job for job in parsed_jobs if job.linkedin_job_id or job.linkedin_job_url]

                    logger.info(
                        "email parsed | run_id=%s | gmail_message_id=%s | subject=%r | template=%r | extracted_jobs=%s",
                        run_id,
                        message_id,
                        subject,
                        linkedin_template,
                        len(parsed_jobs),
                    )
                    self._event(
                        events_repo,
                        run_id,
                        "info",
                        "message_parsed",
                        "Email parsed",
                        {
                            "gmail_message_id": message_id,
                            "subject": subject,
                            "template": linkedin_template,
                            "extracted_jobs": len(parsed_jobs),
                        },
                    )

                    if not parsed_jobs:
                        raise ValueError("No jobs extracted from email.")

                    for parsed in parsed_jobs:
                        if dedup_service.is_duplicate(parsed):
                            run.total_duplicates += 1
                            run.total_processed += 1
                            logger.info(
                                "duplicate job detected | run_id=%s | gmail_message_id=%s | subject=%r | template=%r | linkedin_job_id=%s",
                                run_id,
                                message_id,
                                subject,
                                linkedin_template,
                                parsed.linkedin_job_id,
                            )
                            continue

                        try:
                            jobs_repo.create(**parsed.model_dump())
                            run.total_inserted += 1
                            run.total_processed += 1
                            logger.info(
                                "job inserted | run_id=%s | gmail_message_id=%s | subject=%r | template=%r | linkedin_job_id=%s | title=%r",
                                run_id,
                                message_id,
                                subject,
                                linkedin_template,
                                parsed.linkedin_job_id,
                                parsed.title,
                            )
                        except IntegrityError:
                            db.rollback()
                            run.total_duplicates += 1
                            run.total_processed += 1
                            logger.info(
                                "duplicate job on insert | run_id=%s | gmail_message_id=%s | subject=%r | template=%r | linkedin_job_id=%s",
                                run_id,
                                message_id,
                                subject,
                                linkedin_template,
                                parsed.linkedin_job_id,
                            )
                            self._event(
                                events_repo,
                                run_id,
                                "info",
                                "duplicate_on_insert",
                                "Duplicate detected on insert",
                                {
                                    "gmail_message_id": message_id,
                                    "linkedin_job_id": parsed.linkedin_job_id,
                                },
                            )

                    processed_repo.create_or_ignore(
                        gmail_message_id=message_id,
                        run_id=run_id,
                        email_subject=subject,
                        linkedin_template=linkedin_template,
                        outcome="processed",
                    )
                    run = run_repo.save(run)
                    self._event(
                        events_repo,
                        run_id,
                        "info",
                        "message_processing_completed",
                        "Gmail message processed",
                        {
                            "gmail_message_id": message_id,
                            "subject": subject,
                            "template": linkedin_template,
                        },
                    )
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    run.total_failed += 1
                    run.total_processed += 1
                    error_summary = self.error_service.classify(exc)
                    failure_repo.create(
                        run_id=run_id,
                        gmail_message_id=message_id,
                        stage=error_summary,
                        error_message=str(exc),
                        payload_excerpt=f"subject={subject!r} template={linkedin_template!r} message_id={message_id}",
                    )
                    logger.exception(
                        "sync item failed | run_id=%s | gmail_message_id=%s | subject=%r | template=%r | error_summary=%s",
                        run_id,
                        message_id,
                        subject,
                        linkedin_template,
                        error_summary,
                    )
                    self._event(
                        events_repo,
                        run_id,
                        "error",
                        "message_processing_failed",
                        "Gmail message processing failed",
                        {
                            "gmail_message_id": message_id,
                            "subject": subject,
                            "template": linkedin_template,
                            **self.error_service.payload(exc),
                        },
                    )
                    run = run_repo.save(run)

            logger.info(
                "gmail sync completed | run_id=%s | found=%s | processed=%s | inserted=%s | duplicates=%s | failed=%s",
                run_id,
                run.total_found,
                run.total_processed,
                run.total_inserted,
                run.total_duplicates,
                run.total_failed,
            )
            self._event(
                events_repo,
                run_id,
                "info",
                "sync_completed",
                "Gmail sync completed",
                {
                    "found": run.total_found,
                    "processed": run.total_processed,
                    "inserted": run.total_inserted,
                    "duplicates": run.total_duplicates,
                    "failed": run.total_failed,
                },
            )
            run_repo.mark_completed(run)
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            error_summary = self.error_service.classify(exc)
            logger.exception("sync failed | run_id=%s | error_summary=%s", run_id, error_summary)
            self._event(
                events_repo,
                run_id,
                "error",
                "sync_failed",
                "Gmail sync failed",
                self.error_service.payload(exc),
            )
            run_repo.mark_failed(run, error_summary)
        finally:
            db.close()

    def _find_message_ids(self, events_repo: SyncRunEventRepository, run_id: int) -> tuple[str, list[str]]:
        candidate_queries = self.gmail_client.build_relaxed_queries()
        if not candidate_queries:
            candidate_queries = [self.gmail_client.build_query()]

        aggregate: list[str] = []
        seen: set[str] = set()
        last_query = candidate_queries[0]
        attempt = 0

        def run_query(candidate_query: str, attempt: int) -> list[str]:
            logger.info("gmail query attempt | run_id=%s | attempt=%s | query=%s", run_id, attempt, candidate_query)
            self._event(events_repo, run_id, "info", "gmail_query_attempt", "Attempting Gmail query", {"attempt": attempt, "query": candidate_query})
            ids = self.retry_service.run(
                lambda candidate_query=candidate_query: self.gmail_client.list_message_ids(candidate_query, settings.gmail_max_results),
                should_retry=self.error_service.is_transient,
                on_retry=lambda retry_attempt, exc, delay, candidate_query=candidate_query: self._handle_retry(
                    events_repo,
                    run_id,
                    "list_message_ids",
                    retry_attempt,
                    exc,
                    delay,
                    {"query": candidate_query},
                ),
            )
            logger.info(
                "gmail query result | run_id=%s | attempt=%s | query=%s | total_found=%s",
                run_id,
                attempt,
                candidate_query,
                len(ids),
            )
            self._event(
                events_repo,
                run_id,
                "info",
                "gmail_query_result",
                "Gmail query returned messages",
                {"attempt": attempt, "query": candidate_query, "total_found": len(ids)},
            )
            return ids

        for candidate_query in candidate_queries:
            attempt += 1
            ids = run_query(candidate_query, attempt)
            last_query = candidate_query
            for message_id in ids:
                if message_id not in seen:
                    seen.add(message_id)
                    aggregate.append(message_id)
                if len(aggregate) >= settings.gmail_max_results:
                    break
            if len(aggregate) >= settings.gmail_max_results:
                break

        if not aggregate and settings.enable_broad_linkedin_fallback:
            broad_query = self.gmail_client.build_broad_linkedin_fallback_query()
            if broad_query and broad_query not in candidate_queries:
                attempt += 1
                ids = run_query(broad_query, attempt)
                last_query = broad_query
                for message_id in ids:
                    if message_id not in seen:
                        seen.add(message_id)
                        aggregate.append(message_id)
                    if len(aggregate) >= settings.gmail_max_results:
                        break
        return last_query, aggregate[: settings.gmail_max_results]

    def _handle_retry(
        self,
        events_repo: SyncRunEventRepository,
        run_id: int,
        operation: str,
        attempt: int,
        exc: Exception,
        delay: float,
        extra_payload: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "operation": operation,
            "attempt": attempt,
            "delay_seconds": round(delay, 2),
            **self.error_service.payload(exc),
        }
        if extra_payload:
            payload.update(extra_payload)
        logger.warning(
            "retry scheduled | run_id=%s | operation=%s | attempt=%s | delay=%.2fs | error_summary=%s",
            run_id,
            operation,
            attempt,
            delay,
            self.error_service.classify(exc),
        )
        self._event(events_repo, run_id, "warning", "retry_scheduled", "Retry scheduled for transient error", payload)

    def _event(
        self,
        events_repo: SyncRunEventRepository,
        run_id: int,
        level: str,
        event_type: str,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        try:
            events_repo.create(run_id=run_id, level=level, event_type=event_type, message=message, payload=payload)
        except Exception:  # noqa: BLE001
            logger.exception("failed to persist sync event | run_id=%s | event_type=%s", run_id, event_type)

    def _find_first_job_link(self, content: str) -> str | None:
        import re

        match = re.search(r'https?://[^\s">]+/jobs/view/\d+/?[^\s">]*', content or '', flags=re.IGNORECASE)
        return match.group(0) if match else None

    def _should_process_message(self, headers: dict[str, str], bodies: dict[str, str]) -> tuple[bool, str]:
        sender = (headers.get("From") or "").lower()
        template = (headers.get("X-LinkedIn-Template") or "").strip()
        subject = (headers.get("Subject") or "").lower()
        content = (bodies.get("text") or "") + "\n" + (bodies.get("html") or "")
        has_job_link = bool(self._find_first_job_link(content))

        configured_job_senders = {item.strip().lower() for item in settings.gmail_sender_filters.split(",") if item.strip()}
        configured_job_senders.update({"jobalerts-noreply@linkedin.com"})
        allowed_sender_contains = [item.strip().lower() for item in settings.allowed_sender_contains.split(",") if item.strip()]
        is_configured_job_sender = any(sender.endswith(addr) or addr in sender for addr in configured_job_senders)
        sender_matches_allowed_contains = any(fragment in sender for fragment in allowed_sender_contains) if allowed_sender_contains else True

        if not sender_matches_allowed_contains:
            return False, "unsupported_sender"
        if template in self.NON_JOB_TEMPLATES:
            return False, "non_job_template"
        if template in self.JOB_TEMPLATES:
            return True, "supported_job_template"
        if has_job_link and is_configured_job_sender:
            return True, "job_link_from_supported_sender"
        if has_job_link and template.startswith("email_job"):
            return True, "job_link_from_job_template_family"
        if has_job_link and ("cargo de" in subject or "vaga" in subject or "oportunidade" in subject or "candidate-se" in subject or "candidatura" in subject):
            return True, "job_link_subject_match"
        return False, "missing_job_signal"
