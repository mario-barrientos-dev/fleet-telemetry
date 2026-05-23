"""Integration test fixtures.

These tests boot a real Postgres via testcontainers and run Alembic migrations
against it. A session-scoped container is shared; each test runs in its own
transaction-cleared database state via `truncate_all`.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config as AlembicConfig
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from testcontainers.postgres import PostgresContainer

from alembic import command
from app.application.previous_event_cache import PreviousEventCache
from app.application.use_cases.ingest_telemetry import IngestTelemetry
from app.application.use_cases.transition_to_fault import TransitionToFault
from app.application.vehicle_locks import VehicleLockMap
from app.domain.services.anomaly_detector import RuleBasedAnomalyDetector
from app.infrastructure.clock import SystemClock
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.ids import UUIDv7Generator

BACKEND_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    raw = postgres_container.get_connection_url()
    # testcontainers returns psycopg URLs; rewrite for asyncpg
    return raw.replace("postgresql+psycopg2", "postgresql+asyncpg").replace(
        "postgresql://", "postgresql+asyncpg://"
    )


@pytest.fixture(scope="session", autouse=True)
def _run_migrations(database_url: str) -> None:
    os.environ["APP_DATABASE_URL"] = database_url
    cfg = AlembicConfig(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(database_url, future=True)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


@pytest_asyncio.fixture(autouse=True)
async def truncate_all(engine: AsyncEngine) -> AsyncIterator[None]:
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE anomalies, maintenance_records, missions, "
                "zone_entries, vehicles_current, telemetry_events RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def ids() -> UUIDv7Generator:
    return UUIDv7Generator()


@pytest.fixture
def clock() -> SystemClock:
    return SystemClock()


@pytest_asyncio.fixture
async def transition_to_fault(
    session_factory: async_sessionmaker[AsyncSession],
    ids: UUIDv7Generator,
    clock: SystemClock,
) -> TransitionToFault:
    return TransitionToFault(
        uow_factory=lambda isolation=None: SqlAlchemyUnitOfWork(
            session_factory, isolation=isolation
        ),
        clock=clock,
        ids=ids,
    )


@pytest_asyncio.fixture
async def ingest(
    session_factory: async_sessionmaker[AsyncSession],
    ids: UUIDv7Generator,
    clock: SystemClock,
    transition_to_fault: TransitionToFault,
) -> IngestTelemetry:
    return IngestTelemetry(
        uow_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        locks=VehicleLockMap(),
        cache=PreviousEventCache(),
        detector=RuleBasedAnomalyDetector(ids=ids),
        clock=clock,
        ids=ids,
        transition_to_fault=transition_to_fault,
    )
