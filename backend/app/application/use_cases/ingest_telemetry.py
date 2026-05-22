"""Ingest one telemetry event.

ADR-0006 (idempotency via UNIQUE (vehicle_id, ts) + ON CONFLICT).
ADR-0007 (in-proc asyncio.Lock per vehicle_id).
ADR-0009 (in-memory cache of last event per vehicle).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from app.application.previous_event_cache import PreviousEventCache
from app.application.use_cases.transition_to_fault import (
    TransitionToFault,
    TransitionToFaultCommand,
)
from app.application.vehicle_locks import VehicleLockMap
from app.domain.entities import TelemetryEvent, VehicleSnapshot
from app.domain.ports import Clock, IdGenerator
from app.domain.services.anomaly_detector import AnomalyDetector
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

IngestUoWFactory = Callable[[], SqlAlchemyUnitOfWork]


@dataclass(frozen=True, slots=True)
class IngestResult:
    event_id: UUID
    duplicate: bool
    anomalies_detected: list[str]
    zone_counted: bool


@dataclass(frozen=True, slots=True)
class IngestTelemetryCommand:
    event: TelemetryEvent


class IngestTelemetry:
    def __init__(
        self,
        *,
        uow_factory: IngestUoWFactory,
        locks: VehicleLockMap,
        cache: PreviousEventCache,
        detector: AnomalyDetector,
        clock: Clock,
        ids: IdGenerator,
        transition_to_fault: TransitionToFault,
    ) -> None:
        self._uow_factory = uow_factory
        self._locks = locks
        self._cache = cache
        self._detector = detector
        self._clock = clock
        self._ids = ids
        self._transition_to_fault = transition_to_fault

    async def execute(self, cmd: IngestTelemetryCommand) -> IngestResult:
        event = cmd.event
        lock = await self._locks.acquire(event.vehicle_id)

        async with lock:
            previous = self._cache.get(event.vehicle_id)
            event_id = self._ids.next()
            anomalies_persisted: list[str] = []
            zone_counted = False
            duplicate = False

            uow: SqlAlchemyUnitOfWork
            async with self._uow_factory() as uow:
                inserted_id = await uow.telemetry.insert_with_id(event_id, event)
                if inserted_id is None:
                    existing = await uow.telemetry.get_existing_id(event.vehicle_id, event.ts)
                    assert existing is not None
                    await uow.commit()
                    return IngestResult(
                        event_id=existing,
                        duplicate=True,
                        anomalies_detected=[],
                        zone_counted=False,
                    )

                await uow.snapshots.upsert(
                    VehicleSnapshot(
                        vehicle_id=event.vehicle_id,
                        status=event.status,
                        battery_pct=event.battery_pct,
                        last_event_id=inserted_id,
                        last_seen_at=event.ts,
                        last_lat=event.lat,
                        last_lon=event.lon,
                    )
                )

                if event.zone_entered is not None:
                    zone_counted = await uow.zones.add(
                        entry_id=self._ids.next(),
                        zone_id=event.zone_entered,
                        vehicle_id=event.vehicle_id,
                        source_event_id=inserted_id,
                        entered_at=event.ts,
                    )

                anomalies = self._detector.detect(event, previous, source_event_id=inserted_id)
                if anomalies:
                    await uow.anomalies.add_many(anomalies)
                    anomalies_persisted = [a.kind for a in anomalies]

                await uow.commit()

            if event.status == "fault":
                await self._transition_to_fault.execute(
                    TransitionToFaultCommand(
                        vehicle_id=event.vehicle_id,
                        source_event_id=event_id,
                        error_codes=event.error_codes,
                        reason="telemetry status=fault",
                    )
                )

            self._cache.set(event)

            return IngestResult(
                event_id=event_id,
                duplicate=duplicate,
                anomalies_detected=anomalies_persisted,
                zone_counted=zone_counted,
            )
