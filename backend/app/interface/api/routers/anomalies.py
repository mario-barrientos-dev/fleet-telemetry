from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query

from app.config import get_settings
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.interface.api.schemas import AnomaliesOut, AnomalyOut

router = APIRouter(prefix="/api/v1", tags=["anomalies"])


@router.get("/anomalies", response_model=AnomaliesOut)
async def list_anomalies(
    vehicle_id: str | None = None,
    kind: str | None = None,
    severity: str | None = None,
    ts_from: datetime | None = Query(default=None, alias="from"),
    ts_to: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=100, ge=1, le=500),
) -> AnomaliesOut:
    settings = get_settings()
    now = datetime.now(UTC)
    window = timedelta(hours=settings.polling_anomaly_window_hours)
    effective_from = ts_from or (now - window)
    effective_to = ts_to or now

    factory = get_session_factory()
    async with SqlAlchemyUnitOfWork(factory) as uow:
        rows = await uow.anomalies.list(
            vehicle_id=vehicle_id,
            kind=kind,
            severity=severity,
            ts_from=effective_from,
            ts_to=effective_to,
            limit=limit,
        )

    data = [
        AnomalyOut(
            id=a.id,
            vehicle_id=a.vehicle_id,
            ts=a.ts,
            kind=a.kind,
            severity=a.severity,
            details=dict(a.details),
            source_event_id=a.source_event_id,
        )
        for a in rows
    ]
    return AnomaliesOut(data=data)
