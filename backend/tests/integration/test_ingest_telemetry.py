from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.application.use_cases.ingest_telemetry import (
    IngestTelemetry,
    IngestTelemetryCommand,
)
from app.domain.entities import TelemetryEvent
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration


def _event(*, vehicle_id: str, ts: datetime, **overrides: object) -> TelemetryEvent:
    base: dict[str, object] = {
        "vehicle_id": vehicle_id,
        "ts": ts,
        "lat": 37.41,
        "lon": -122.08,
        "battery_pct": 80,
        "speed_mps": 1.0,
        "status": "moving",
        "error_codes": (),
        "zone_entered": None,
    }
    base.update(overrides)
    return TelemetryEvent(**base)  # type: ignore[arg-type]


async def test_ingest_persists_event_and_snapshot(
    ingest: IngestTelemetry,
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    ts = datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC)
    result = await ingest.execute(IngestTelemetryCommand(event=_event(vehicle_id="v-1", ts=ts)))
    assert result.duplicate is False
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        snap = await uow.snapshots.get("v-1")
    assert snap is not None
    assert snap.status == "moving"
    assert snap.battery_pct == 80


async def test_ingest_is_idempotent_on_duplicate_vehicle_ts(
    ingest: IngestTelemetry,
) -> None:
    ts = datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC)
    first = await ingest.execute(IngestTelemetryCommand(event=_event(vehicle_id="v-1", ts=ts)))
    second = await ingest.execute(IngestTelemetryCommand(event=_event(vehicle_id="v-1", ts=ts)))
    assert second.duplicate is True
    assert second.event_id == first.event_id


async def test_zone_entered_increments_counter(
    ingest: IngestTelemetry,
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    ts = datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC)
    await ingest.execute(
        IngestTelemetryCommand(event=_event(vehicle_id="v-1", ts=ts, zone_entered="charging_bay_1"))
    )
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        counts = await uow.zones.counts()
    assert counts.get("charging_bay_1") == 1
