from __future__ import annotations


class DomainError(Exception):
    """Base for all domain-level errors. Carries a stable code for HTTP mapping."""

    code: str = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvariantViolationError(DomainError):
    code = "invariant_violation"


class DuplicateTelemetryError(DomainError):
    code = "duplicate_telemetry"


class UnknownZoneError(DomainError):
    code = "unknown_zone"


class VehicleNotFoundError(DomainError):
    code = "vehicle_not_found"


class IllegalStateTransitionError(DomainError):
    code = "illegal_state_transition"
