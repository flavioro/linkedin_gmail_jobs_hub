from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.domain.models import SyncRun
from app.persistence.db import Base
from app.persistence.repositories.sync_runs import SyncRunRepository


def test_sync_run_save_persists_mutations_without_rollback():
    engine = create_engine("sqlite:///:memory:")
    TestingSession = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    repo = SyncRunRepository(db)

    run = repo.create_run("queued")
    run.total_found = 3
    run.total_inserted = 2

    saved = repo.save(run)

    assert saved.total_found == 3
    assert saved.total_inserted == 2
    db.close()
