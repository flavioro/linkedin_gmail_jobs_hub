from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.persistence.db import Base, engine, ensure_schema_upgrades

configure_logging()
app = FastAPI(title=settings.app_name)
app.include_router(api_router, prefix=settings.api_v1_str)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema_upgrades()
