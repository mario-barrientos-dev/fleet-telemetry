"""REQ-F-008: fault transition is atomic and idempotent under concurrency.

Two concurrent triggers for the same vehicle (different source_event_ids,
mimicking a near-duplicate alert path) must result in:

- exactly one mission cancelled,
- *one* maintenance record per source_event_id (the second is its own record,
  because the UNIQUE key is on triggered_by_event_id),
- the vehicle status is `fault`,

When the *same* source_event_id is delivered twice the second call is
idempotent and returns the existing record without creating a new one.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.application.use_cases.transition_to_fault import (
    TransitionToFault,
    TransitionToFaultCommand,
)
from app.domain.entities import Mission, TelemetryEvent
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.ids import UUIDv7Generator

pytestmark = pytest.mark.integration


async def _seed_vehicle_with_event_and_active_mission(
    session_factory,  # type: ignore[no-untyped-def]
    *,
    vehicle_id: str,
    event_id: UUID,
) -> None:
    ts = datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC)
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        # Telemetry row required for FK from maintenance_records.triggered_by_event_id
        await uow.telemetry.insert_with_id(
            event_id,
            TelemetryEvent(
                vehicle_id=vehicle_id,
                ts=ts,
                lat=0.0,
                lon=0.0,
                battery_pct=80,
                speed_mps=0.0,
                status="moving",
            ),
        )
        ids = UUIDv7Generator()
        await uow.missions.create(
            Mission(
                id=ids.next(),
                vehicle_id=vehicle_id,
                status="active",
                started_at=ts,
                ended_at=None,
            )
        )
        # Seed snapshot so set_status_for_update has a row to lock
        from app.domain.entities import VehicleSnapshot

        await uow.snapshots.upsert(
            VehicleSnapshot(
                vehicle_id=vehicle_id,
                status="moving",
                battery_pct=80,
                last_event_id=event_id,
                last_seen_at=ts,
                last_lat=0.0,
                last_lon=0.0,
            )
        )
        await uow.commit()


async def test_same_source_event_id_is_idempotent(
    transition_to_fault: TransitionToFault,
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    event_id = uuid4()
    await _seed_vehicle_with_event_and_active_mission(
        session_factory, vehicle_id="v-1", event_id=event_id
    )

    cmd = TransitionToFaultCommand(vehicle_id="v-1", source_event_id=event_id, error_codes=("E_X",))

    a, b = await asyncio.gather(
        transition_to_fault.execute(cmd),
        transition_to_fault.execute(cmd),
    )
    # Same record id from both (one created, one idempotent)
    assert a.maintenance_record_id == b.maintenance_record_id
    assert (a.idempotent, b.idempotent) in [(False, True), (True, False)]

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        # Only one active mission existed; it should now be cancelled
        from sqlalchemy import func, select

        from app.infrastructure.db.models import MaintenanceRow, MissionRow

        active_count = (
            await uow.session.execute(select(func.count()).where(MissionRow.status == "active"))
        ).scalar_one()
        maint_count = (
            await uow.session.execute(select(func.count()).select_from(MaintenanceRow))
        ).scalar_one()

    assert active_count == 0, "active mission should be cancelled"
    assert maint_count == 1, "exactly one maintenance record"


async def test_concurrent_distinct_event_ids_each_create_their_record(
    transition_to_fault: TransitionToFault,
    session_factory,  # type: ignore[no-untyped-def]
) -> None:
    event_a, event_b = uuid4(), uuid4()
    await _seed_vehicle_with_event_and_active_mission(
        session_factory, vehicle_id="v-1", event_id=event_a
    )
    # Seed a second telemetry row so event_b satisfies the FK
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await uow.telemetry.insert_with_id(
            event_b,
            TelemetryEvent(
                vehicle_id="v-1",
                ts=datetime(2026, 5, 22, 10, 0, 1, tzinfo=UTC),
                lat=0.0,
                lon=0.0,
                battery_pct=80,
                speed_mps=0.0,
                status="moving",
            ),
        )
        await uow.commit()

    cmd_a = TransitionToFaultCommand(vehicle_id="v-1", source_event_id=event_a)
    cmd_b = TransitionToFaultCommand(vehicle_id="v-1", source_event_id=event_b)

    await asyncio.gather(
        transition_to_fault.execute(cmd_a),
        transition_to_fault.execute(cmd_b),
    )

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        from sqlalchemy import func, select

        from app.infrastructure.db.models import MaintenanceRow, MissionRow

        active_count = (
            await uow.session.execute(select(func.count()).where(MissionRow.status == "active"))
        ).scalar_one()
        maint_count = (
            await uow.session.execute(select(func.count()).select_from(MaintenanceRow))
        ).scalar_one()

    assert active_count == 0, "only one mission existed, it must be cancelled exactly once"
    assert maint_count == 2, "one maintenance record per distinct source_event_id"
