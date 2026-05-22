"""Dependency wiring.

Singletons live on `app.state` (set in `main.create_app`). Per-request callables
return them so FastAPI can resolve them via `Depends`.
"""

from __future__ import annotations

from fastapi import Request

from app.application.previous_event_cache import PreviousEventCache
from app.application.use_cases.ingest_telemetry import IngestTelemetry
from app.application.use_cases.transition_to_fault import TransitionToFault
from app.application.vehicle_locks import VehicleLockMap
from app.domain.services.anomaly_detector import RuleBasedAnomalyDetector
from app.infrastructure.clock import SystemClock
from app.infrastructure.ids import UUIDv7Generator


class AppState:
    """Holds singletons assembled at startup."""

    def __init__(
        self,
        *,
        locks: VehicleLockMap,
        cache: PreviousEventCache,
        detector: RuleBasedAnomalyDetector,
        ingest: IngestTelemetry,
        transition_to_fault: TransitionToFault,
        clock: SystemClock,
        ids: UUIDv7Generator,
    ) -> None:
        self.locks = locks
        self.cache = cache
        self.detector = detector
        self.ingest = ingest
        self.transition_to_fault = transition_to_fault
        self.clock = clock
        self.ids = ids


def get_app_state(request: Request) -> AppState:
    state: AppState = request.app.state.app_state
    return state


def get_ingest_use_case(request: Request) -> IngestTelemetry:
    return get_app_state(request).ingest


def get_transition_to_fault(request: Request) -> TransitionToFault:
    return get_app_state(request).transition_to_fault
