"""Atomic vehicle → fault transition.

ADR-0005 (SERIALIZABLE + bounded retry; defense-in-depth via partial unique
index on `missions(vehicle_id) WHERE status='active'` and UNIQUE on
`maintenance_records.triggered_by_event_id`).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

import structlog
from sqlalchemy.exc import DBAPIError

from app.domain.entities import MaintenanceRecord
from app.domain.ports import Clock, IdGenerator
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork

FaultUoWFactory = Callable[..., SqlAlchemyUnitOfWork]

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TransitionToFaultCommand:
    vehicle_id: str
    source_event_id: UUID
    error_codes: tuple[str, ...] = ()
    reason: str = "status transition to fault"


@dataclass(frozen=True, slots=True)
class TransitionToFaultResult:
    vehicle_id: str
    maintenance_record_id: UUID
    cancelled_mission_id: UUID | None
    idempotent: bool


class TransitionToFault:
    """Cancels active mission + creates maintenance record under SERIALIZABLE.

    Retries up to `max_retries` times on Postgres `serialization_failure`
    (SQLSTATE 40001). The operation is idempotent on
    `(triggered_by_event_id) UNIQUE` so a duplicate execution returns the
    existing record without creating a new one.
    """

    def __init__(
        self,
        *,
        uow_factory: FaultUoWFactory,
        clock: Clock,
        ids: IdGenerator,
        max_retries: int = 3,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids
        self._max_retries = max_retries

    async def execute(self, cmd: TransitionToFaultCommand) -> TransitionToFaultResult:
        attempt = 0
        while True:
            try:
                return await self._run_once(cmd)
            except DBAPIError as e:
                if not _is_serialization_failure(e):
                    raise
                attempt += 1
                if attempt > self._max_retries:
                    log.error(
                        "transition_to_fault.retry_exhausted",
                        vehicle_id=cmd.vehicle_id,
                        attempts=attempt,
                    )
                    raise
                log.warning(
                    "transition_to_fault.retry",
                    vehicle_id=cmd.vehicle_id,
                    attempt=attempt,
                )
                await asyncio.sleep(0.01 * attempt)

    async def _run_once(self, cmd: TransitionToFaultCommand) -> TransitionToFaultResult:
        async with self._uow_factory(isolation="SERIALIZABLE") as uow:
            existing = await uow.maintenance.get_for_event(cmd.source_event_id)
            if existing is not None:
                await uow.commit()
                return TransitionToFaultResult(
                    vehicle_id=cmd.vehicle_id,
                    maintenance_record_id=existing.id,
                    cancelled_mission_id=None,
                    idempotent=True,
                )

            active = await uow.missions.get_active_for_update(cmd.vehicle_id)
            cancelled_mission_id: UUID | None = None
            if active is not None:
                await uow.missions.cancel(active.id, self._clock.now())
                cancelled_mission_id = active.id

            await uow.snapshots.set_status_for_update(cmd.vehicle_id, "fault")

            record = MaintenanceRecord(
                id=self._ids.next(),
                vehicle_id=cmd.vehicle_id,
                triggered_by_event_id=cmd.source_event_id,
                reason=cmd.reason,
                error_codes=tuple(cmd.error_codes),
                created_at=self._clock.now(),
            )
            await uow.maintenance.add(record)
            await uow.commit()

            return TransitionToFaultResult(
                vehicle_id=cmd.vehicle_id,
                maintenance_record_id=record.id,
                cancelled_mission_id=cancelled_mission_id,
                idempotent=False,
            )


def _is_serialization_failure(error: DBAPIError) -> bool:
    pgcode = getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)
    return pgcode == "40001"
