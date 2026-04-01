from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.models import ProcessedGmailMessage


class ProcessedGmailMessageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_existing_ids(self, gmail_message_ids: list[str]) -> set[str]:
        if not gmail_message_ids:
            return set()
        stmt = select(ProcessedGmailMessage.gmail_message_id).where(ProcessedGmailMessage.gmail_message_id.in_(gmail_message_ids))
        return {row[0] for row in self.db.execute(stmt).all()}

    def create_or_ignore(
        self,
        *,
        gmail_message_id: str,
        run_id: int | None = None,
        email_subject: str | None = None,
        linkedin_template: str | None = None,
        outcome: str = "processed",
    ) -> ProcessedGmailMessage | None:
        item = ProcessedGmailMessage(
            gmail_message_id=gmail_message_id,
            run_id=run_id,
            email_subject=email_subject,
            linkedin_template=linkedin_template,
            outcome=outcome,
        )
        try:
            self.db.add(item)
            self.db.commit()
            self.db.refresh(item)
            return item
        except IntegrityError:
            self.db.rollback()
            return None
