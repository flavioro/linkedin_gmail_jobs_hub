from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_api_key
from app.domain.schemas import IgnoredEmailRead, IgnoredEmailReasonSummary
from app.persistence.repositories.unknown_email_templates import UnknownEmailTemplateRepository

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get('', response_model=list[IgnoredEmailRead])
def list_ignored_emails(
    db: Session = Depends(get_db),
    reason: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[IgnoredEmailRead]:
    repo = UnknownEmailTemplateRepository(db)
    return [IgnoredEmailRead.model_validate(item) for item in repo.list_items(reason=reason, limit=limit, offset=offset)]


@router.get('/by-reason', response_model=list[IgnoredEmailReasonSummary])
def ignored_email_summary_by_reason(db: Session = Depends(get_db)) -> list[IgnoredEmailReasonSummary]:
    repo = UnknownEmailTemplateRepository(db)
    return [IgnoredEmailReasonSummary(**item) for item in repo.count_by_reason()]
