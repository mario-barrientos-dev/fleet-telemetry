from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.zones import ZONES_SET


class TelemetryIn(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "vehicle_id": "v-12",
                    "timestamp": "2026-05-22T10:30:00Z",
                    "lat": 37.41,
                    "lon": -122.08,
                    "battery_pct": 78,
                    "speed_mps": 1.2,
                    "status": "moving",
                    "error_codes": [],
                    "zone_entered": "charging_bay_1",
                }
            ]
        }
    )

    vehicle_id: str = Field(min_length=1, max_length=50)
    timestamp: AwareDatetime
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    battery_pct: int = Field(ge=0, le=100)
    speed_mps: float = Field(ge=0)
    status: Literal["idle", "moving", "charging", "fault"]
    error_codes: list[str] = Field(default_factory=list)
    zone_entered: str | None = None

    @field_validator("zone_entered")
    @classmethod
    def _zone_in_set(cls, v: str | None) -> str | None:
        if v is not None and v not in ZONES_SET:
            raise ValueError(f"zone_entered must be one of the {len(ZONES_SET)} known zones")
        return v


class TelemetryAccepted(BaseModel):
    event_id: UUID
    duplicate: bool
    anomalies_detected: list[str]
    zone_counted: bool


class VehicleStatusUpdateIn(BaseModel):
    status: Literal["idle", "moving", "charging", "fault"]
    error_codes: list[str] = Field(default_factory=list)
    reason: str = "operator escalation"


class VehicleStatusUpdateOut(BaseModel):
    vehicle_id: str
    maintenance_record_id: UUID | None = None
    cancelled_mission_id: UUID | None = None
    idempotent: bool = False


class FleetStatusOut(BaseModel):
    counts: dict[Literal["idle", "moving", "charging", "fault"], int]
    total: int
    as_of: datetime


class AnomalyLite(BaseModel):
    kind: str
    severity: str
    ts: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class VehicleOut(BaseModel):
    vehicle_id: str
    status: str
    battery_pct: int
    last_seen_at: datetime
    last_lat: float
    last_lon: float
    last_anomaly: AnomalyLite | None = None


class VehiclesOut(BaseModel):
    data: list[VehicleOut]


class ZoneCountOut(BaseModel):
    zone_id: str
    entry_count: int


class ZoneCountsOut(BaseModel):
    data: list[ZoneCountOut]
    as_of: datetime


class AnomalyOut(BaseModel):
    id: UUID
    vehicle_id: str
    ts: datetime
    kind: str
    severity: str
    details: dict[str, Any]
    source_event_id: UUID | None


class AnomaliesOut(BaseModel):
    data: list[AnomalyOut]
