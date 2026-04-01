from sqlalchemy.orm import Session

from app.domain.models import ParseFailure


class ParseFailureRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, **kwargs) -> ParseFailure:
        failure = ParseFailure(**kwargs)
        self.db.add(failure)
        self.db.commit()
        self.db.refresh(failure)
        return failure
