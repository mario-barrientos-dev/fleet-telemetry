from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.entities import (
    Anomaly,
    MaintenanceRecord,
    Mission,
    TelemetryEvent,
    VehicleSnapshot,
    VehicleStatus,
)


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    def next(self) -> UUID: ...


class TelemetryRepository(Protocol):
    async def insert_if_absent(self, event: TelemetryEvent) -> UUID | None:
        """Insert; return the new id, or None if a row with same (vehicle_id, ts) existed."""

    async def get_existing_id(self, vehicle_id: str, ts: datetime) -> UUID | None: ...


class VehicleSnapshotRepository(Protocol):
    async def upsert(self, snapshot: VehicleSnapshot) -> None: ...
    async def get(self, vehicle_id: str) -> VehicleSnapshot | None: ...
    async def list_all(self) -> Sequence[VehicleSnapshot]: ...
    async def counts_by_status(self) -> dict[VehicleStatus, int]: ...
    async def set_status_for_update(self, vehicle_id: str, status: VehicleStatus) -> None:
        """Locks the row (SELECT FOR UPDATE inside the same transaction) and updates status."""


class ZoneEntryRepository(Protocol):
    async def add(
        self,
        *,
        entry_id: UUID,
        zone_id: str,
        vehicle_id: str,
        source_event_id: UUID,
        entered_at: datetime,
    ) -> bool:
        """Insert one entry. Return False if the source_event_id was already counted."""

    async def counts(self) -> dict[str, int]: ...


class MissionRepository(Protocol):
    async def get_active_for_update(self, vehicle_id: str) -> Mission | None: ...
    async def cancel(self, mission_id: UUID, ended_at: datetime) -> None: ...
    async def create(self, mission: Mission) -> None: ...


class MaintenanceRepository(Protocol):
    async def get_for_event(self, source_event_id: UUID) -> MaintenanceRecord | None: ...
    async def add(self, record: MaintenanceRecord) -> None: ...


class AnomalyRepository(Protocol):
    async def add_many(self, anomalies: Sequence[Anomaly]) -> None: ...
    async def list(
        self,
        *,
        vehicle_id: str | None,
        kind: str | None,
        severity: str | None,
        ts_from: datetime,
        ts_to: datetime,
        limit: int,
    ) -> Sequence[Anomaly]: ...
    async def last_per_vehicle(self) -> dict[str, Anomaly]: ...


class UnitOfWork(Protocol):
    telemetry: TelemetryRepository
    snapshots: VehicleSnapshotRepository
    zones: ZoneEntryRepository
    missions: MissionRepository
    maintenance: MaintenanceRepository
    anomalies: AnomalyRepository

    async def __aenter__(self) -> UnitOfWork: ...
    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
