"""In-memory cache: vehicle_id → last accepted TelemetryEvent.

Updated **after** a successful commit by the ingest use case. On startup the
cache is rehydrated from `vehicles_current` / `telemetry_events` so the very
first event after restart still has context. Trade-off documented in ADR-0009.
"""

from __future__ import annotations

from app.domain.entities import TelemetryEvent


class PreviousEventCache:
    def __init__(self) -> None:
        self._by_vehicle: dict[str, TelemetryEvent] = {}

    def get(self, vehicle_id: str) -> TelemetryEvent | None:
        return self._by_vehicle.get(vehicle_id)

    def set(self, event: TelemetryEvent) -> None:
        self._by_vehicle[event.vehicle_id] = event

    def hydrate(self, events: dict[str, TelemetryEvent]) -> None:
        self._by_vehicle.update(events)

    def __len__(self) -> int:
        return len(self._by_vehicle)
