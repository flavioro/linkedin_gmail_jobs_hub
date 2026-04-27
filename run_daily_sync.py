from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.persistence.db import Base, SessionLocal, engine, ensure_schema_upgrades  # noqa: E402
from app.persistence.repositories.sync_runs import SyncRunRepository  # noqa: E402
from app.services.job_csv_export_service import JobCsvExportService  # noqa: E402
from app.services.sync_service import SyncService  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("run_daily_sync")


def main() -> int:
    logger.info("Inicializando banco e schema...")
    Base.metadata.create_all(bind=engine)
    ensure_schema_upgrades()

    db = SessionLocal()
    try:
        runs_repo = SyncRunRepository(db)
        run = runs_repo.create_run(status="queued")
        run_id = run.id
        logger.info("Run criado com ID=%s", run_id)
    finally:
        db.close()

    logger.info("Iniciando sincronização do Gmail...")
    SyncService().run_sync(run_id)

    db = SessionLocal()
    try:
        runs_repo = SyncRunRepository(db)
        final_run = runs_repo.get_by_id(run_id)
        if not final_run:
            logger.error("Run %s não encontrado ao final da execução.", run_id)
            return 2

        logger.info(
            "Execução finalizada | run_id=%s | status=%s | total_found=%s | total_processed=%s | total_inserted=%s | total_duplicates=%s | total_failed=%s",
            final_run.id,
            final_run.status,
            final_run.total_found,
            final_run.total_processed,
            final_run.total_inserted,
            final_run.total_duplicates,
            final_run.total_failed,
        )

        if final_run.status != "completed":
            logger.error("Sincronização terminou com status '%s'.", final_run.status)
            return 1

        export_result = JobCsvExportService().export_recent_jobs(db)
        logger.info(
            "CSV exportado com sucesso | dias=%s | linhas=%s | arquivo=%s",
            export_result.days,
            export_result.row_count,
            export_result.output_path,
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
