from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.application.use_cases.ingest_telemetry import (
    IngestTelemetry,
    IngestTelemetryCommand,
)
from app.domain.entities import TelemetryEvent
from app.interface.api.dependencies import get_ingest_use_case
from app.interface.api.schemas import TelemetryAccepted, TelemetryIn

router = APIRouter(prefix="/api/v1", tags=["telemetry"])


@router.post(
    "/telemetry",
    response_model=TelemetryAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_telemetry(
    body: TelemetryIn,
    use_case: IngestTelemetry = Depends(get_ingest_use_case),
) -> TelemetryAccepted:
    event = TelemetryEvent(
        vehicle_id=body.vehicle_id,
        ts=body.timestamp,
        lat=body.lat,
        lon=body.lon,
        battery_pct=body.battery_pct,
        speed_mps=body.speed_mps,
        status=body.status,
        error_codes=tuple(body.error_codes),
        zone_entered=body.zone_entered,
    )
    result = await use_case.execute(IngestTelemetryCommand(event=event))
    return TelemetryAccepted(
        event_id=result.event_id,
        duplicate=result.duplicate,
        anomalies_detected=result.anomalies_detected,
        zone_counted=result.zone_counted,
    )
