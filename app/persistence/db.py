from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


if settings.db_url.startswith("sqlite:///"):
    db_path = settings.db_url.replace("sqlite:///", "", 1)
    if db_path and db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False} if settings.db_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _sqlite_jobs_has_unique_gmail_message_id(conn) -> bool:
    rows = conn.execute(text("PRAGMA index_list('jobs')")).fetchall()
    for row in rows:
        row_map = getattr(row, "_mapping", None)
        index_name = row_map["name"] if row_map else row[1]
        is_unique = bool(row_map["unique"] if row_map else row[2])
        if not is_unique:
            continue
        info_rows = conn.execute(text(f"PRAGMA index_info('{index_name}')")).fetchall()
        columns = []
        for info in info_rows:
            info_map = getattr(info, "_mapping", None)
            columns.append(info_map["name"] if info_map else info[2])
        if columns == ["gmail_message_id"]:
            return True
    return False


def _rebuild_jobs_table_sqlite(conn) -> None:
    conn.execute(text("DROP TABLE IF EXISTS jobs__new"))
    conn.execute(
        text(
            """
            CREATE TABLE jobs__new (
                id INTEGER NOT NULL PRIMARY KEY,
                gmail_message_id VARCHAR(255) NOT NULL,
                external_message_id VARCHAR(255),
                linkedin_job_id VARCHAR(64),
                linkedin_job_url VARCHAR(1024),
                raw_email_link VARCHAR(1024),
                email_subject VARCHAR(512),
                linkedin_template VARCHAR(255),
                parser_used VARCHAR(128),
                title VARCHAR(512),
                company VARCHAR(255),
                location_raw VARCHAR(255),
                seniority VARCHAR(32) NOT NULL DEFAULT 'nao_informado',
                work_model VARCHAR(32) NOT NULL DEFAULT 'nao_informado',
                received_at DATETIME,
                body_html_hash VARCHAR(128),
                status VARCHAR(32) NOT NULL DEFAULT 'new',
                raw_metadata_json TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    )
    conn.execute(
        text(
            """
            INSERT INTO jobs__new (
                id, gmail_message_id, external_message_id, linkedin_job_id, linkedin_job_url, raw_email_link,
                email_subject, linkedin_template, parser_used, title, company, location_raw, seniority, work_model,
                received_at, body_html_hash, status, raw_metadata_json, created_at, updated_at
            )
            SELECT
                id, gmail_message_id, external_message_id, linkedin_job_id, linkedin_job_url, raw_email_link,
                email_subject, linkedin_template, parser_used, title, company, location_raw, seniority, work_model,
                received_at, body_html_hash, status, raw_metadata_json, created_at, updated_at
            FROM jobs
            """
        )
    )
    conn.execute(text("DROP TABLE jobs"))
    conn.execute(text("ALTER TABLE jobs__new RENAME TO jobs"))


def ensure_schema_upgrades() -> None:
    if not settings.db_url.startswith("sqlite"):
        return

    with engine.begin() as conn:
        inspector = inspect(conn)
        existing_tables = set(inspector.get_table_names())

        if "jobs" in existing_tables:
            columns = {col["name"] for col in inspector.get_columns("jobs")}
            alterations = {
                "raw_email_link": "ALTER TABLE jobs ADD COLUMN raw_email_link VARCHAR(1024)",
                "email_subject": "ALTER TABLE jobs ADD COLUMN email_subject VARCHAR(512)",
                "linkedin_template": "ALTER TABLE jobs ADD COLUMN linkedin_template VARCHAR(255)",
                "parser_used": "ALTER TABLE jobs ADD COLUMN parser_used VARCHAR(128)",
            }
            for name, sql in alterations.items():
                if name not in columns:
                    conn.execute(text(sql))

            if _sqlite_jobs_has_unique_gmail_message_id(conn):
                _rebuild_jobs_table_sqlite(conn)

        if "sync_run_events" not in existing_tables:
            conn.execute(text(
                """
                CREATE TABLE sync_run_events (
                    id INTEGER NOT NULL PRIMARY KEY,
                    run_id INTEGER NOT NULL,
                    level VARCHAR(32) NOT NULL,
                    event_type VARCHAR(64) NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            ))

        if "processed_gmail_messages" not in existing_tables:
            conn.execute(text(
                """
                CREATE TABLE processed_gmail_messages (
                    id INTEGER NOT NULL PRIMARY KEY,
                    gmail_message_id VARCHAR(255) NOT NULL UNIQUE,
                    run_id INTEGER,
                    email_subject VARCHAR(512),
                    linkedin_template VARCHAR(255),
                    outcome VARCHAR(32) NOT NULL DEFAULT 'processed',
                    processed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            ))

        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_gmail_message_id ON jobs (gmail_message_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_linkedin_job_id ON jobs (linkedin_job_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_linkedin_job_url ON jobs (linkedin_job_url)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_linkedin_template ON jobs (linkedin_template)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs (status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sync_run_events_run_id ON sync_run_events (run_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_sync_run_events_event_type ON sync_run_events (event_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_processed_gmail_messages_gmail_message_id ON processed_gmail_messages (gmail_message_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_processed_gmail_messages_run_id ON processed_gmail_messages (run_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_processed_gmail_messages_linkedin_template ON processed_gmail_messages (linkedin_template)"))
