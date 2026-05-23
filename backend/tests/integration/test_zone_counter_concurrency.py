"""REQ-F-005: every zone entry is counted under concurrency.

Scenario from the spec: at shift change, multiple vehicles converge on the
same charging bay in the same second. We simulate 50 concurrent ingests, one
per vehicle, all naming the same zone, and assert the counter is exactly 50.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.application.use_cases.ingest_telemetry import (
    IngestTelemetry,
    IngestTelemetryCommand,
)
from app.domain.entities import TelemetryEvent
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration


async def test_50_concurrent_vehicles_entering_same_zone_count_50(
    ingest: IngestTelemetry,
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    base_ts = datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC)
    zone = "charging_bay_1"

    async def one(i: int) -> None:
        event = TelemetryEvent(
            vehicle_id=f"v-{i}",
            ts=base_ts + timedelta(milliseconds=i),
            lat=37.41,
            lon=-122.08,
            battery_pct=80,
            speed_mps=0.0,
            status="charging",
            zone_entered=zone,
        )
        await ingest.execute(IngestTelemetryCommand(event=event))

    await asyncio.gather(*(one(i) for i in range(1, 51)))

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        counts = await uow.zones.counts()
    assert counts.get(zone) == 50, (
        f"Expected 50 entries for {zone}, got {counts.get(zone)}. "
        "This indicates a lost zone entry under concurrent ingestion."
    )


async def test_replaying_the_same_event_does_not_double_count(
    ingest: IngestTelemetry,
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    ts = datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC)
    event = TelemetryEvent(
        vehicle_id="v-1",
        ts=ts,
        lat=37.41,
        lon=-122.08,
        battery_pct=80,
        speed_mps=0.0,
        status="charging",
        zone_entered="charging_bay_1",
    )
    await ingest.execute(IngestTelemetryCommand(event=event))
    await ingest.execute(IngestTelemetryCommand(event=event))
    await ingest.execute(IngestTelemetryCommand(event=event))

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        counts = await uow.zones.counts()
    assert counts.get("charging_bay_1") == 1
