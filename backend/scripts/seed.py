from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.domain.entities import Mission, TelemetryEvent, VehicleSnapshot
from app.infrastructure.clock import SystemClock
from app.infrastructure.db.session import dispose_engine, get_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.ids import UUIDv7Generator


async def seed_fleet(num_vehicles: int = 50) -> None:
    clock = SystemClock()
    ids = UUIDv7Generator()
    now = clock.now()
    factory = get_session_factory()

    async with SqlAlchemyUnitOfWork(factory) as uow:
        for i in range(1, num_vehicles + 1):
            vehicle_id = f"v-{i}"
            existing = await uow.snapshots.get(vehicle_id)
            if existing is not None:
                continue

            event_id = ids.next()
            event = TelemetryEvent(
                vehicle_id=vehicle_id,
                ts=now,
                lat=37.41 + (i % 10) * 0.0001,
                lon=-122.08 + (i % 10) * 0.0001,
                battery_pct=80,
                speed_mps=0.0,
                status="idle",
                error_codes=(),
                zone_entered=None,
            )
            inserted = await uow.telemetry.insert_with_id(event_id, event)
            assert inserted is not None

            await uow.snapshots.upsert(
                VehicleSnapshot(
                    vehicle_id=vehicle_id,
                    status="idle",
                    battery_pct=80,
                    last_event_id=event_id,
                    last_seen_at=now,
                    last_lat=event.lat,
                    last_lon=event.lon,
                )
            )

            mission = Mission(
                id=ids.next(),
                vehicle_id=vehicle_id,
                status="active",
                started_at=now,
                ended_at=None,
            )
            await uow.missions.create(mission)

        await uow.commit()


async def _main() -> None:
    try:
        await seed_fleet()
        print(f"seed: ok @ {datetime.now(UTC).isoformat()}")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(_main())
