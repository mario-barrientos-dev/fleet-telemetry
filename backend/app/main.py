from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.application.previous_event_cache import PreviousEventCache
from app.application.use_cases.ingest_telemetry import IngestTelemetry
from app.application.use_cases.transition_to_fault import TransitionToFault
from app.application.vehicle_locks import VehicleLockMap
from app.config import get_settings
from app.domain.services.anomaly_detector import RuleBasedAnomalyDetector
from app.infrastructure.clock import SystemClock
from app.infrastructure.db.session import dispose_engine, get_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.ids import UUIDv7Generator
from app.infrastructure.logging import configure_logging
from app.interface.api.dependencies import AppState
from app.interface.api.error_handlers import install_error_handlers
from app.interface.api.routers import admin, anomalies, fleet, health, telemetry, zones

log = structlog.get_logger(__name__)


async def _hydrate_previous_event_cache(cache: PreviousEventCache) -> None:
    factory = get_session_factory()
    async with SqlAlchemyUnitOfWork(factory) as uow:
        # Best-effort: rehydrate from the last seen snapshot. The detector tolerates
        # an empty cache (first event per vehicle simply lacks `previous`).
        snapshots = await uow.snapshots.list_all()
    log.info("startup.cache.hydrate", vehicles_with_snapshot=len(snapshots))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    factory = get_session_factory()
    clock = SystemClock()
    ids = UUIDv7Generator()
    locks = VehicleLockMap()
    cache = PreviousEventCache()
    detector = RuleBasedAnomalyDetector(ids=ids)

    transition_to_fault = TransitionToFault(
        uow_factory=lambda isolation=None: SqlAlchemyUnitOfWork(factory, isolation=isolation),
        clock=clock,
        ids=ids,
    )
    ingest = IngestTelemetry(
        uow_factory=lambda: SqlAlchemyUnitOfWork(factory),
        locks=locks,
        cache=cache,
        detector=detector,
        clock=clock,
        ids=ids,
        transition_to_fault=transition_to_fault,
    )

    await _hydrate_previous_event_cache(cache)

    app.state.app_state = AppState(
        locks=locks,
        cache=cache,
        detector=detector,
        ingest=ingest,
        transition_to_fault=transition_to_fault,
        clock=clock,
        ids=ids,
    )

    log.info("api.startup", environment=settings.environment)
    try:
        yield
    finally:
        await dispose_engine()
        log.info("api.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Fleet Telemetry API",
        version="0.1.0",
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)

    app.include_router(health.router)
    app.include_router(telemetry.router)
    app.include_router(fleet.router)
    app.include_router(zones.router)
    app.include_router(anomalies.router)
    app.include_router(admin.router)

    return app


app = create_app()
