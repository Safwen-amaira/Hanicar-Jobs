from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api import (
    applications,
    candidates,
    companies,
    health,
    meta,
    opportunities,
    opportunity_types,
    sources,
)
from app.core.config import get_settings
from app.db.base import Base
from app.db.seed import run_startup_seeds
from app.db.session import AsyncSessionLocal, engine
import app.models  # noqa: F401 - register models


async def _ensure_application_tracker_columns() -> None:
    async with engine.begin() as conn:
        dialect = conn.dialect.name
        if dialect == "postgresql":
            for value in (
                "prepared",
                "applied",
                "interviewing",
                "offer",
                "rejected",
                "withdrawn",
            ):
                await conn.execute(
                    text(f"ALTER TYPE application_status ADD VALUE IF NOT EXISTS '{value}'")
                )

        def current_columns(sync_conn):
            inspector = inspect(sync_conn)
            if "applications" not in inspector.get_table_names():
                return set()
            return {col["name"] for col in inspector.get_columns("applications")}

        columns = await conn.run_sync(current_columns)
        additions = {
            "applied_at": "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "DATETIME",
            "interview_at": "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "DATETIME",
            "decision_at": "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "DATETIME",
            "next_action_at": "TIMESTAMP WITH TIME ZONE" if dialect == "postgresql" else "DATETIME",
            "contact_name": "VARCHAR(255) DEFAULT ''",
            "contact_email": "VARCHAR(320) DEFAULT ''",
            "notes": "TEXT DEFAULT ''",
        }
        for name, ddl in additions.items():
            if name not in columns:
                await conn.execute(text(f"ALTER TABLE applications ADD COLUMN {name} {ddl}"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables for compose boot (alembic also available)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_application_tracker_columns()
    async with AsyncSessionLocal() as session:
        await run_startup_seeds(session)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=settings.tagline,
        version=settings.version,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(meta.router)
    app.include_router(opportunity_types.router)
    app.include_router(candidates.router)
    app.include_router(companies.router)
    app.include_router(opportunities.router)
    app.include_router(applications.router)
    app.include_router(sources.router)
    return app


app = create_app()
