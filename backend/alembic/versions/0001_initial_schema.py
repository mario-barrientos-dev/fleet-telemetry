"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-22

Creates all tables for the fleet-telemetry vertical slice.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    vehicle_status = postgresql.ENUM(
        "idle", "moving", "charging", "fault", name="vehicle_status"
    )
    mission_status = postgresql.ENUM(
        "active", "cancelled", "completed", name="mission_status"
    )
    vehicle_status.create(op.get_bind(), checkfirst=True)
    mission_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "telemetry_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vehicle_id", sa.String(50), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("battery_pct", sa.SmallInteger(), nullable=False),
        sa.Column("speed_mps", sa.Float(), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("idle", "moving", "charging", "fault", name="vehicle_status", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "error_codes",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("zone_entered", sa.String(), nullable=True),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("vehicle_id", "ts", name="uq_telemetry_vehicle_ts"),
        sa.CheckConstraint("battery_pct BETWEEN 0 AND 100", name="ck_telemetry_battery_pct"),
        sa.CheckConstraint("speed_mps >= 0", name="ck_telemetry_speed_nonneg"),
    )
    op.create_index("ix_telemetry_vehicle_ts", "telemetry_events", ["vehicle_id", "ts"])
    op.create_index("ix_telemetry_ts", "telemetry_events", ["ts"])

    op.create_table(
        "vehicles_current",
        sa.Column("vehicle_id", sa.String(50), primary_key=True),
        sa.Column(
            "status",
            postgresql.ENUM("idle", "moving", "charging", "fault", name="vehicle_status", create_type=False),
            nullable=False,
        ),
        sa.Column("battery_pct", sa.SmallInteger(), nullable=False),
        sa.Column(
            "last_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("telemetry_events.id"),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_lat", sa.Float(), nullable=False),
        sa.Column("last_lon", sa.Float(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_vehicles_status", "vehicles_current", ["status"])

    op.create_table(
        "zone_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", sa.String(), nullable=False),
        sa.Column("vehicle_id", sa.String(50), nullable=False),
        sa.Column(
            "source_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("telemetry_events.id"),
            nullable=False,
        ),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_event_id", name="uq_zone_entries_source_event"),
    )
    op.create_index("ix_zone_entries_zone", "zone_entries", ["zone_id"])

    op.create_table(
        "missions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vehicle_id", sa.String(50), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM("active", "cancelled", "completed", name="mission_status", create_type=False),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'active' AND ended_at IS NULL) OR "
            "(status <> 'active' AND ended_at IS NOT NULL)",
            name="ck_missions_active_ended_at",
        ),
    )
    op.create_index(
        "uq_one_active_mission_per_vehicle",
        "missions",
        ["vehicle_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "maintenance_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vehicle_id", sa.String(50), nullable=False),
        sa.Column(
            "triggered_by_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("telemetry_events.id"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column(
            "error_codes",
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "triggered_by_event_id", name="uq_maintenance_triggered_by_event"
        ),
    )
    op.create_index(
        "ix_maintenance_vehicle", "maintenance_records", ["vehicle_id", "created_at"]
    )

    op.create_table(
        "anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("vehicle_id", sa.String(50), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column(
            "details",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "source_event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("telemetry_events.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_anomalies_vehicle_ts", "anomalies", ["vehicle_id", "ts"])
    op.create_index("ix_anomalies_ts", "anomalies", ["ts"])


def downgrade() -> None:
    op.drop_index("ix_anomalies_ts", table_name="anomalies")
    op.drop_index("ix_anomalies_vehicle_ts", table_name="anomalies")
    op.drop_table("anomalies")

    op.drop_index("ix_maintenance_vehicle", table_name="maintenance_records")
    op.drop_table("maintenance_records")

    op.drop_index("uq_one_active_mission_per_vehicle", table_name="missions")
    op.drop_table("missions")

    op.drop_index("ix_zone_entries_zone", table_name="zone_entries")
    op.drop_table("zone_entries")

    op.drop_index("ix_vehicles_status", table_name="vehicles_current")
    op.drop_table("vehicles_current")

    op.drop_index("ix_telemetry_ts", table_name="telemetry_events")
    op.drop_index("ix_telemetry_vehicle_ts", table_name="telemetry_events")
    op.drop_table("telemetry_events")

    op.execute("DROP TYPE IF EXISTS mission_status")
    op.execute("DROP TYPE IF EXISTS vehicle_status")
