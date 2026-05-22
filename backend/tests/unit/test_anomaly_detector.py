from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.domain.entities import TelemetryEvent
from app.domain.services.anomaly_detector import RuleBasedAnomalyDetector
from tests.unit.fakes import SequentialIdGenerator


def _event(
    *,
    ts: datetime | None = None,
    battery: int = 80,
    speed: float = 0.0,
    status: str = "moving",
    error_codes: tuple[str, ...] = (),
    lat: float = 0.0,
    lon: float = 0.0,
) -> TelemetryEvent:
    return TelemetryEvent(
        vehicle_id="v-1",
        ts=ts or datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC),
        lat=lat,
        lon=lon,
        battery_pct=battery,
        speed_mps=speed,
        status=status,  # type: ignore[arg-type]
        error_codes=error_codes,
    )


@pytest.fixture
def detector() -> RuleBasedAnomalyDetector:
    return RuleBasedAnomalyDetector(SequentialIdGenerator())


def test_no_previous_event_produces_no_anomalies_for_stateful_rules(
    detector: RuleBasedAnomalyDetector,
) -> None:
    curr = _event(battery=80, speed=1.0)
    assert detector.detect(curr, previous=None) == []


def test_low_battery_is_edge_triggered(detector: RuleBasedAnomalyDetector) -> None:
    prev = _event(battery=16, speed=1.0, lat=0.0, lon=0.0)
    curr = _event(battery=10, speed=1.0, lat=0.001, lon=0.001)
    kinds = {a.kind for a in detector.detect(curr, prev)}
    assert "low_battery" in kinds


def test_low_battery_not_repeated_below_threshold(
    detector: RuleBasedAnomalyDetector,
) -> None:
    prev = _event(battery=10, speed=1.0, lat=0.0, lon=0.0)
    curr = _event(battery=9, speed=1.0, lat=0.001, lon=0.001)
    kinds = {a.kind for a in detector.detect(curr, prev)}
    assert "low_battery" not in kinds


def test_battery_increase_without_charging_is_critical(
    detector: RuleBasedAnomalyDetector,
) -> None:
    prev = _event(battery=50)
    curr = _event(battery=60, status="moving")
    kinds = [a.kind for a in detector.detect(curr, prev)]
    assert "battery_anomaly" in kinds


def test_battery_increase_while_charging_is_ok(detector: RuleBasedAnomalyDetector) -> None:
    prev = _event(battery=50, status="charging", speed=0.0)
    curr = _event(battery=60, status="charging", speed=0.0)
    assert detector.detect(curr, prev) == []


def test_sudden_battery_drop_is_critical(detector: RuleBasedAnomalyDetector) -> None:
    prev = _event(battery=80, ts=datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC))
    curr = _event(battery=55, ts=datetime(2026, 5, 22, 10, 0, 1, tzinfo=UTC))
    kinds = [a.kind for a in detector.detect(curr, prev)]
    assert "battery_anomaly" in kinds


def test_stuck_when_moving_no_position_change(detector: RuleBasedAnomalyDetector) -> None:
    prev = _event(status="moving", speed=0.0, lat=1.0, lon=2.0)
    curr = _event(status="moving", speed=0.0, lat=1.0, lon=2.0)
    kinds = [a.kind for a in detector.detect(curr, prev)]
    assert "stuck" in kinds


def test_overspeed(detector: RuleBasedAnomalyDetector) -> None:
    curr = _event(speed=3.5, status="moving")
    kinds = [a.kind for a in detector.detect(curr, previous=None)]
    assert "overspeed" in kinds


def test_status_inconsistency_idle_with_speed(detector: RuleBasedAnomalyDetector) -> None:
    curr = _event(status="idle", speed=0.5)
    kinds = [a.kind for a in detector.detect(curr, previous=None)]
    assert "status_inconsistency" in kinds


def test_fault_with_errors(detector: RuleBasedAnomalyDetector) -> None:
    curr = _event(status="fault", error_codes=("E_BATT",), speed=0.0)
    kinds = [a.kind for a in detector.detect(curr, previous=None)]
    assert "fault_with_errors" in kinds


def test_fault_without_errors_is_not_an_anomaly_by_itself(
    detector: RuleBasedAnomalyDetector,
) -> None:
    curr = _event(status="fault", error_codes=(), speed=0.0)
    kinds = [a.kind for a in detector.detect(curr, previous=None)]
    assert "fault_with_errors" not in kinds


@given(speed=st.floats(min_value=3.01, max_value=20, allow_nan=False, allow_infinity=False))
def test_overspeed_property(speed: float) -> None:
    detector = RuleBasedAnomalyDetector(SequentialIdGenerator())
    curr = _event(speed=speed, status="moving")
    kinds = {a.kind for a in detector.detect(curr, previous=None)}
    assert "overspeed" in kinds


@given(speed=st.floats(min_value=0, max_value=3.0, allow_nan=False, allow_infinity=False))
def test_no_overspeed_at_or_below_threshold(speed: float) -> None:
    detector = RuleBasedAnomalyDetector(SequentialIdGenerator())
    curr = _event(speed=speed, status="moving")
    kinds = {a.kind for a in detector.detect(curr, previous=None)}
    assert "overspeed" not in kinds


def test_detector_assigns_distinct_ids(detector: RuleBasedAnomalyDetector) -> None:
    prev = _event(battery=16, speed=0)
    curr = _event(
        battery=10, speed=5.0, status="idle", error_codes=()
    )  # low_battery + overspeed + status_inconsistency
    anomalies = detector.detect(curr, prev)
    ids = [a.id for a in anomalies]
    assert len(ids) == len(set(ids))


def test_battery_drop_outside_window_is_not_flagged(detector: RuleBasedAnomalyDetector) -> None:
    prev = _event(battery=80, ts=datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC))
    curr = _event(
        battery=50,
        ts=datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC) + timedelta(seconds=60),
    )
    kinds = {a.kind for a in detector.detect(curr, prev)}
    assert "battery_anomaly" not in kinds
