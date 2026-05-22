from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

VEHICLE_STATUS_ENUM = ENUM(
    "idle", "moving", "charging", "fault", name="vehicle_status", create_type=True
)
MISSION_STATUS_ENUM = ENUM(
    "active", "cancelled", "completed", name="mission_status", create_type=True
)


class Base(DeclarativeBase):
    pass


class TelemetryEventRow(Base):
    __tablename__ = "telemetry_events"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(String(50), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    battery_pct: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    speed_mps: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(VEHICLE_STATUS_ENUM, nullable=False)
    error_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::text[]")
    )
    zone_entered: Mapped[str | None] = mapped_column(String, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("vehicle_id", "ts", name="uq_telemetry_vehicle_ts"),
        CheckConstraint("battery_pct BETWEEN 0 AND 100", name="ck_telemetry_battery_pct"),
        CheckConstraint("speed_mps >= 0", name="ck_telemetry_speed_nonneg"),
        Index("ix_telemetry_vehicle_ts", "vehicle_id", "ts"),
        Index("ix_telemetry_ts", "ts"),
    )


class VehicleSnapshotRow(Base):
    __tablename__ = "vehicles_current"
    vehicle_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    status: Mapped[str] = mapped_column(VEHICLE_STATUS_ENUM, nullable=False)
    battery_pct: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    last_event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("telemetry_events.id"),
        nullable=False,
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_lat: Mapped[float] = mapped_column(Float, nullable=False)
    last_lon: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_vehicles_status", "status"),)


class ZoneEntryRow(Base):
    __tablename__ = "zone_entries"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    zone_id: Mapped[str] = mapped_column(String, nullable=False)
    vehicle_id: Mapped[str] = mapped_column(String(50), nullable=False)
    source_event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("telemetry_events.id"),
        nullable=False,
    )
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("source_event_id", name="uq_zone_entries_source_event"),
        Index("ix_zone_entries_zone", "zone_id"),
    )


class MissionRow(Base):
    __tablename__ = "missions"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(MISSION_STATUS_ENUM, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(status = 'active' AND ended_at IS NULL) OR "
            "(status <> 'active' AND ended_at IS NOT NULL)",
            name="ck_missions_active_ended_at",
        ),
        Index(
            "uq_one_active_mission_per_vehicle",
            "vehicle_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )


class MaintenanceRow(Base):
    __tablename__ = "maintenance_records"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(String(50), nullable=False)
    triggered_by_event_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("telemetry_events.id"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(String, nullable=False)
    error_codes: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'::text[]")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("triggered_by_event_id", name="uq_maintenance_triggered_by_event"),
        Index("ix_maintenance_vehicle", "vehicle_id", "created_at"),
    )


class AnomalyRow(Base):
    __tablename__ = "anomalies"
    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    vehicle_id: Mapped[str] = mapped_column(String(50), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    source_event_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("telemetry_events.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_anomalies_vehicle_ts", "vehicle_id", "ts"),
        Index("ix_anomalies_ts", "ts"),
    )
