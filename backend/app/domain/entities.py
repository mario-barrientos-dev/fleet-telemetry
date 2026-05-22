from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from app.domain.errors import InvariantViolationError, UnknownZoneError
from app.zones import ZONES_SET

VehicleStatus = Literal["idle", "moving", "charging", "fault"]
MissionStatus = Literal["active", "cancelled", "completed"]
AnomalyKind = Literal[
    "low_battery",
    "battery_anomaly",
    "stuck",
    "overspeed",
    "status_inconsistency",
    "fault_with_errors",
]
Severity = Literal["info", "warning", "critical"]

VALID_STATUSES: frozenset[str] = frozenset({"idle", "moving", "charging", "fault"})


@dataclass(frozen=True, slots=True)
class TelemetryEvent:
    vehicle_id: str
    ts: datetime
    lat: float
    lon: float
    battery_pct: int
    speed_mps: float
    status: VehicleStatus
    error_codes: tuple[str, ...] = ()
    zone_entered: str | None = None

    def __post_init__(self) -> None:
        if not self.vehicle_id:
            raise InvariantViolationError("vehicle_id cannot be empty")
        if self.ts.tzinfo is None:
            raise InvariantViolationError("timestamp must be timezone-aware (UTC)")
        if not (0 <= self.battery_pct <= 100):
            raise InvariantViolationError("battery_pct must be between 0 and 100")
        if self.speed_mps < 0:
            raise InvariantViolationError("speed_mps must be non-negative")
        if not (-90.0 <= self.lat <= 90.0):
            raise InvariantViolationError("lat out of range")
        if not (-180.0 <= self.lon <= 180.0):
            raise InvariantViolationError("lon out of range")
        if self.status not in VALID_STATUSES:
            raise InvariantViolationError(f"unknown status: {self.status}")
        if self.zone_entered is not None and self.zone_entered not in ZONES_SET:
            raise UnknownZoneError(f"zone_entered '{self.zone_entered}' is not a known zone")


@dataclass(frozen=True, slots=True)
class VehicleSnapshot:
    vehicle_id: str
    status: VehicleStatus
    battery_pct: int
    last_event_id: UUID
    last_seen_at: datetime
    last_lat: float
    last_lon: float


@dataclass(frozen=True, slots=True)
class Mission:
    id: UUID
    vehicle_id: str
    status: MissionStatus
    started_at: datetime
    ended_at: datetime | None

    def __post_init__(self) -> None:
        if self.status == "active" and self.ended_at is not None:
            raise InvariantViolationError("active mission cannot have ended_at")
        if self.status != "active" and self.ended_at is None:
            raise InvariantViolationError("non-active mission must have ended_at")


@dataclass(frozen=True, slots=True)
class MaintenanceRecord:
    id: UUID
    vehicle_id: str
    triggered_by_event_id: UUID
    reason: str
    error_codes: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Anomaly:
    id: UUID
    vehicle_id: str
    ts: datetime
    kind: AnomalyKind
    severity: Severity
    details: dict[str, object] = field(default_factory=dict)
    source_event_id: UUID | None = None
