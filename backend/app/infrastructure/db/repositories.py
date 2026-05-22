from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities import (
    Anomaly,
    AnomalyKind,
    MaintenanceRecord,
    Mission,
    MissionStatus,
    Severity,
    TelemetryEvent,
    VehicleSnapshot,
    VehicleStatus,
)
from app.infrastructure.db.models import (
    AnomalyRow,
    MaintenanceRow,
    MissionRow,
    TelemetryEventRow,
    VehicleSnapshotRow,
    ZoneEntryRow,
)


def _row_to_mission(row: MissionRow) -> Mission:
    return Mission(
        id=row.id,
        vehicle_id=row.vehicle_id,
        status=cast(MissionStatus, row.status),
        started_at=row.started_at,
        ended_at=row.ended_at,
    )


def _row_to_snapshot(row: VehicleSnapshotRow) -> VehicleSnapshot:
    return VehicleSnapshot(
        vehicle_id=row.vehicle_id,
        status=cast(VehicleStatus, row.status),
        battery_pct=row.battery_pct,
        last_event_id=row.last_event_id,
        last_seen_at=row.last_seen_at,
        last_lat=row.last_lat,
        last_lon=row.last_lon,
    )


def _row_to_anomaly(row: AnomalyRow) -> Anomaly:
    return Anomaly(
        id=row.id,
        vehicle_id=row.vehicle_id,
        ts=row.ts,
        kind=cast(AnomalyKind, row.kind),
        severity=cast(Severity, row.severity),
        details=dict(row.details),
        source_event_id=row.source_event_id,
    )


class SqlTelemetryRepository:
    def __init__(self, session: AsyncSession, *, id_factory: type[UUID] = UUID) -> None:
        self._s = session
        self._id_factory = id_factory  # placeholder; ids come from outside

    async def insert_if_absent(self, event: TelemetryEvent) -> UUID | None:
        raise NotImplementedError  # use insert_with_id

    async def insert_with_id(self, event_id: UUID, event: TelemetryEvent) -> UUID | None:
        stmt = (
            pg_insert(TelemetryEventRow)
            .values(
                id=event_id,
                vehicle_id=event.vehicle_id,
                ts=event.ts,
                lat=event.lat,
                lon=event.lon,
                battery_pct=event.battery_pct,
                speed_mps=event.speed_mps,
                status=event.status,
                error_codes=list(event.error_codes),
                zone_entered=event.zone_entered,
            )
            .on_conflict_do_nothing(constraint="uq_telemetry_vehicle_ts")
            .returning(TelemetryEventRow.id)
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none()

    async def get_existing_id(self, vehicle_id: str, ts: datetime) -> UUID | None:
        stmt = select(TelemetryEventRow.id).where(
            TelemetryEventRow.vehicle_id == vehicle_id,
            TelemetryEventRow.ts == ts,
        )
        return (await self._s.execute(stmt)).scalar_one_or_none()


class SqlVehicleSnapshotRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def upsert(self, snapshot: VehicleSnapshot) -> None:
        stmt = (
            pg_insert(VehicleSnapshotRow)
            .values(
                vehicle_id=snapshot.vehicle_id,
                status=snapshot.status,
                battery_pct=snapshot.battery_pct,
                last_event_id=snapshot.last_event_id,
                last_seen_at=snapshot.last_seen_at,
                last_lat=snapshot.last_lat,
                last_lon=snapshot.last_lon,
            )
            .on_conflict_do_update(
                index_elements=[VehicleSnapshotRow.vehicle_id],
                set_={
                    "status": snapshot.status,
                    "battery_pct": snapshot.battery_pct,
                    "last_event_id": snapshot.last_event_id,
                    "last_seen_at": snapshot.last_seen_at,
                    "last_lat": snapshot.last_lat,
                    "last_lon": snapshot.last_lon,
                    "updated_at": text("now()"),
                },
            )
        )
        await self._s.execute(stmt)

    async def get(self, vehicle_id: str) -> VehicleSnapshot | None:
        row = (
            await self._s.execute(
                select(VehicleSnapshotRow).where(VehicleSnapshotRow.vehicle_id == vehicle_id)
            )
        ).scalar_one_or_none()
        return _row_to_snapshot(row) if row else None

    async def list_all(self) -> Sequence[VehicleSnapshot]:
        rows = (
            (
                await self._s.execute(
                    select(VehicleSnapshotRow).order_by(VehicleSnapshotRow.vehicle_id)
                )
            )
            .scalars()
            .all()
        )
        return [_row_to_snapshot(r) for r in rows]

    async def counts_by_status(self) -> dict[VehicleStatus, int]:
        from sqlalchemy import func as f

        stmt = select(VehicleSnapshotRow.status, f.count()).group_by(VehicleSnapshotRow.status)
        rows = (await self._s.execute(stmt)).all()
        out: dict[VehicleStatus, int] = {"idle": 0, "moving": 0, "charging": 0, "fault": 0}
        for status, n in rows:
            out[cast(VehicleStatus, status)] = int(n)
        return out

    async def set_status_for_update(self, vehicle_id: str, status: VehicleStatus) -> None:
        # Lock the row, then update.
        await self._s.execute(
            select(VehicleSnapshotRow)
            .where(VehicleSnapshotRow.vehicle_id == vehicle_id)
            .with_for_update()
        )
        await self._s.execute(
            update(VehicleSnapshotRow)
            .where(VehicleSnapshotRow.vehicle_id == vehicle_id)
            .values(status=status, updated_at=text("now()"))
        )


class SqlZoneEntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(
        self,
        *,
        entry_id: UUID,
        zone_id: str,
        vehicle_id: str,
        source_event_id: UUID,
        entered_at: datetime,
    ) -> bool:
        stmt = (
            pg_insert(ZoneEntryRow)
            .values(
                id=entry_id,
                zone_id=zone_id,
                vehicle_id=vehicle_id,
                source_event_id=source_event_id,
                entered_at=entered_at,
            )
            .on_conflict_do_nothing(constraint="uq_zone_entries_source_event")
            .returning(ZoneEntryRow.id)
        )
        result = await self._s.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def counts(self) -> dict[str, int]:
        from sqlalchemy import func as f

        stmt = select(ZoneEntryRow.zone_id, f.count()).group_by(ZoneEntryRow.zone_id)
        return {zone: int(n) for zone, n in (await self._s.execute(stmt)).all()}


class SqlMissionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_active_for_update(self, vehicle_id: str) -> Mission | None:
        stmt = (
            select(MissionRow)
            .where(MissionRow.vehicle_id == vehicle_id, MissionRow.status == "active")
            .with_for_update()
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _row_to_mission(row) if row else None

    async def cancel(self, mission_id: UUID, ended_at: datetime) -> None:
        await self._s.execute(
            update(MissionRow)
            .where(MissionRow.id == mission_id, MissionRow.status == "active")
            .values(status="cancelled", ended_at=ended_at)
        )

    async def create(self, mission: Mission) -> None:
        self._s.add(
            MissionRow(
                id=mission.id,
                vehicle_id=mission.vehicle_id,
                status=mission.status,
                started_at=mission.started_at,
                ended_at=mission.ended_at,
            )
        )


class SqlMaintenanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_for_event(self, source_event_id: UUID) -> MaintenanceRecord | None:
        row = (
            await self._s.execute(
                select(MaintenanceRow).where(
                    MaintenanceRow.triggered_by_event_id == source_event_id
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return MaintenanceRecord(
            id=row.id,
            vehicle_id=row.vehicle_id,
            triggered_by_event_id=row.triggered_by_event_id,
            reason=row.reason,
            error_codes=tuple(row.error_codes),
            created_at=row.created_at,
        )

    async def add(self, record: MaintenanceRecord) -> None:
        self._s.add(
            MaintenanceRow(
                id=record.id,
                vehicle_id=record.vehicle_id,
                triggered_by_event_id=record.triggered_by_event_id,
                reason=record.reason,
                error_codes=list(record.error_codes),
            )
        )


class SqlAnomalyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add_many(self, anomalies: Sequence[Anomaly]) -> None:
        if not anomalies:
            return
        self._s.add_all(
            [
                AnomalyRow(
                    id=a.id,
                    vehicle_id=a.vehicle_id,
                    ts=a.ts,
                    kind=a.kind,
                    severity=a.severity,
                    details=a.details,
                    source_event_id=a.source_event_id,
                )
                for a in anomalies
            ]
        )

    async def list(
        self,
        *,
        vehicle_id: str | None,
        kind: str | None,
        severity: str | None,
        ts_from: datetime,
        ts_to: datetime,
        limit: int,
    ) -> Sequence[Anomaly]:
        stmt = select(AnomalyRow).where(AnomalyRow.ts >= ts_from, AnomalyRow.ts <= ts_to)
        if vehicle_id:
            stmt = stmt.where(AnomalyRow.vehicle_id == vehicle_id)
        if kind:
            stmt = stmt.where(AnomalyRow.kind == kind)
        if severity:
            stmt = stmt.where(AnomalyRow.severity == severity)
        stmt = stmt.order_by(AnomalyRow.ts.desc(), AnomalyRow.id.desc()).limit(limit)
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_row_to_anomaly(r) for r in rows]

    async def last_per_vehicle(self) -> dict[str, Anomaly]:
        stmt = text(
            """
            SELECT DISTINCT ON (vehicle_id)
                id, vehicle_id, ts, kind, severity, details, source_event_id
            FROM anomalies
            ORDER BY vehicle_id, ts DESC, id DESC
            """
        )
        result = (await self._s.execute(stmt)).mappings().all()
        out: dict[str, Anomaly] = {}
        for r in result:
            out[r["vehicle_id"]] = Anomaly(
                id=r["id"],
                vehicle_id=r["vehicle_id"],
                ts=r["ts"],
                kind=cast(AnomalyKind, r["kind"]),
                severity=cast(Severity, r["severity"]),
                details=dict(r["details"]),
                source_event_id=r["source_event_id"],
            )
        return out
