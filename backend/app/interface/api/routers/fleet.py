from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.infrastructure.db.session import get_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.interface.api.schemas import (
    AnomalyLite,
    FleetStatusOut,
    VehicleOut,
    VehiclesOut,
)

router = APIRouter(prefix="/api/v1", tags=["fleet"])


@router.get("/fleet/status", response_model=FleetStatusOut)
async def fleet_status() -> FleetStatusOut:
    factory = get_session_factory()
    async with SqlAlchemyUnitOfWork(factory) as uow:
        counts = await uow.snapshots.counts_by_status()
    return FleetStatusOut(
        counts=counts,
        total=sum(counts.values()),
        as_of=datetime.now(UTC),
    )


@router.get("/vehicles", response_model=VehiclesOut)
async def list_vehicles() -> VehiclesOut:
    factory = get_session_factory()
    async with SqlAlchemyUnitOfWork(factory) as uow:
        snapshots = await uow.snapshots.list_all()
        last_anomalies = await uow.anomalies.last_per_vehicle()

    data: list[VehicleOut] = []
    for s in snapshots:
        last = last_anomalies.get(s.vehicle_id)
        last_lite = (
            AnomalyLite(
                kind=last.kind,
                severity=last.severity,
                ts=last.ts,
                details=dict(last.details),
            )
            if last is not None
            else None
        )
        data.append(
            VehicleOut(
                vehicle_id=s.vehicle_id,
                status=s.status,
                battery_pct=s.battery_pct,
                last_seen_at=s.last_seen_at,
                last_lat=s.last_lat,
                last_lon=s.last_lon,
                last_anomaly=last_lite,
            )
        )
    return VehiclesOut(data=data)
