from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.domain.entities import Mission, TelemetryEvent
from app.domain.errors import InvariantViolationError, UnknownZoneError


def _ts() -> datetime:
    return datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC)


def test_telemetry_requires_aware_timestamp() -> None:
    with pytest.raises(InvariantViolationError):
        TelemetryEvent(
            vehicle_id="v-1",
            ts=datetime(2026, 5, 22, 10, 0, 0),  # naive
            lat=0,
            lon=0,
            battery_pct=50,
            speed_mps=0,
            status="idle",
        )


def test_telemetry_rejects_out_of_range_battery() -> None:
    with pytest.raises(InvariantViolationError):
        TelemetryEvent(
            vehicle_id="v-1",
            ts=_ts(),
            lat=0,
            lon=0,
            battery_pct=101,
            speed_mps=0,
            status="idle",
        )


def test_telemetry_rejects_negative_speed() -> None:
    with pytest.raises(InvariantViolationError):
        TelemetryEvent(
            vehicle_id="v-1",
            ts=_ts(),
            lat=0,
            lon=0,
            battery_pct=50,
            speed_mps=-0.1,
            status="idle",
        )


def test_telemetry_rejects_unknown_status() -> None:
    with pytest.raises(InvariantViolationError):
        TelemetryEvent(
            vehicle_id="v-1",
            ts=_ts(),
            lat=0,
            lon=0,
            battery_pct=50,
            speed_mps=0,
            status="zooming",  # type: ignore[arg-type]
        )


def test_telemetry_rejects_unknown_zone() -> None:
    with pytest.raises(UnknownZoneError):
        TelemetryEvent(
            vehicle_id="v-1",
            ts=_ts(),
            lat=0,
            lon=0,
            battery_pct=50,
            speed_mps=0,
            status="moving",
            zone_entered="atlantis",
        )


def test_telemetry_accepts_known_zone() -> None:
    event = TelemetryEvent(
        vehicle_id="v-1",
        ts=_ts(),
        lat=0,
        lon=0,
        battery_pct=50,
        speed_mps=0,
        status="moving",
        zone_entered="charging_bay_1",
    )
    assert event.zone_entered == "charging_bay_1"


def test_active_mission_must_have_no_ended_at() -> None:
    with pytest.raises(InvariantViolationError):
        Mission(
            id=UUID(int=1),
            vehicle_id="v-1",
            status="active",
            started_at=_ts(),
            ended_at=_ts(),
        )


def test_non_active_mission_must_have_ended_at() -> None:
    with pytest.raises(InvariantViolationError):
        Mission(
            id=UUID(int=1),
            vehicle_id="v-1",
            status="cancelled",
            started_at=_ts(),
            ended_at=None,
        )
