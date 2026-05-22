"""Deterministic rule-based anomaly detection.

The detector compares the current telemetry event against the immediate previous
event from the same vehicle. Rules are documented in ADR §1 and §3 (evolution
path to a statistical detector). The take-home definition of "real-time" is met
because the detector runs synchronously inside the ingest use case.

Each rule is a pure function `(current, previous) -> Anomaly | None`. The
detector simply runs them all and collects the non-None results.

Thresholds are constants and centralised so they can become env-tunable later
without changing the rule code.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.entities import Anomaly, AnomalyKind, Severity, TelemetryEvent
from app.domain.ports import IdGenerator

LOW_BATTERY_THRESHOLD: int = 15
BATTERY_DROP_PCT: int = 10
BATTERY_DROP_WINDOW_S: float = 2.0
STUCK_SPEED_MPS: float = 0.05
OVERSPEED_MPS: float = 3.0
IDLE_SPEED_MPS: float = 0.1


@dataclass(frozen=True, slots=True)
class _Candidate:
    kind: AnomalyKind
    severity: Severity
    details: dict[str, object]


Rule = Callable[[TelemetryEvent, TelemetryEvent | None], _Candidate | None]


class AnomalyDetector(Protocol):
    def detect(
        self,
        current: TelemetryEvent,
        previous: TelemetryEvent | None,
        *,
        source_event_id: UUID | None = None,
    ) -> list[Anomaly]: ...


def _rule_low_battery(curr: TelemetryEvent, prev: TelemetryEvent | None) -> _Candidate | None:
    if curr.battery_pct >= LOW_BATTERY_THRESHOLD:
        return None
    if prev is not None and prev.battery_pct < LOW_BATTERY_THRESHOLD:
        return None
    return _Candidate(
        kind="low_battery",
        severity="warning",
        details={
            "battery_pct": curr.battery_pct,
            "threshold": LOW_BATTERY_THRESHOLD,
            "edge_triggered": True,
        },
    )


def _rule_battery_anomaly(curr: TelemetryEvent, prev: TelemetryEvent | None) -> _Candidate | None:
    if prev is None:
        return None
    diff = curr.battery_pct - prev.battery_pct
    seconds = (curr.ts - prev.ts).total_seconds()
    if diff > 0 and curr.status != "charging":
        return _Candidate(
            kind="battery_anomaly",
            severity="critical",
            details={
                "battery_pct": curr.battery_pct,
                "previous_battery_pct": prev.battery_pct,
                "reason": "battery_increased_without_charging",
            },
        )
    if diff < -BATTERY_DROP_PCT and 0 < seconds <= BATTERY_DROP_WINDOW_S:
        return _Candidate(
            kind="battery_anomaly",
            severity="critical",
            details={
                "battery_pct": curr.battery_pct,
                "previous_battery_pct": prev.battery_pct,
                "delta_seconds": seconds,
                "reason": "battery_dropped_too_fast",
            },
        )
    return None


def _rule_stuck(curr: TelemetryEvent, prev: TelemetryEvent | None) -> _Candidate | None:
    if curr.status != "moving" or curr.speed_mps >= STUCK_SPEED_MPS:
        return None
    if prev is None:
        return None
    same_position = curr.lat == prev.lat and curr.lon == prev.lon
    if not same_position:
        return None
    return _Candidate(
        kind="stuck",
        severity="warning",
        details={
            "speed_mps": curr.speed_mps,
            "lat": curr.lat,
            "lon": curr.lon,
        },
    )


def _rule_overspeed(curr: TelemetryEvent, _prev: TelemetryEvent | None) -> _Candidate | None:
    if curr.speed_mps <= OVERSPEED_MPS:
        return None
    return _Candidate(
        kind="overspeed",
        severity="critical",
        details={"speed_mps": curr.speed_mps, "threshold": OVERSPEED_MPS},
    )


def _rule_status_inconsistency(
    curr: TelemetryEvent, _prev: TelemetryEvent | None
) -> _Candidate | None:
    if curr.status == "idle" and curr.speed_mps > IDLE_SPEED_MPS:
        return _Candidate(
            kind="status_inconsistency",
            severity="warning",
            details={
                "status": curr.status,
                "speed_mps": curr.speed_mps,
                "threshold": IDLE_SPEED_MPS,
            },
        )
    return None


def _rule_fault_with_errors(
    curr: TelemetryEvent, _prev: TelemetryEvent | None
) -> _Candidate | None:
    if curr.status != "fault" or not curr.error_codes:
        return None
    return _Candidate(
        kind="fault_with_errors",
        severity="critical",
        details={"error_codes": list(curr.error_codes)},
    )


_RULES: tuple[Rule, ...] = (
    _rule_low_battery,
    _rule_battery_anomaly,
    _rule_stuck,
    _rule_overspeed,
    _rule_status_inconsistency,
    _rule_fault_with_errors,
)


class RuleBasedAnomalyDetector:
    def __init__(self, ids: IdGenerator) -> None:
        self._ids = ids

    def detect(
        self,
        current: TelemetryEvent,
        previous: TelemetryEvent | None,
        *,
        source_event_id: UUID | None = None,
    ) -> list[Anomaly]:
        anomalies: list[Anomaly] = []
        for rule in _RULES:
            candidate = rule(current, previous)
            if candidate is None:
                continue
            anomalies.append(
                Anomaly(
                    id=self._ids.next(),
                    vehicle_id=current.vehicle_id,
                    ts=current.ts,
                    kind=candidate.kind,
                    severity=candidate.severity,
                    details=candidate.details,
                    source_event_id=source_event_id,
                )
            )
        return anomalies
