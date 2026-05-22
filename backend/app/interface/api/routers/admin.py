from __future__ import annotations

from fastapi import APIRouter, Depends

from app.application.use_cases.transition_to_fault import (
    TransitionToFault,
    TransitionToFaultCommand,
)
from app.infrastructure.db.session import get_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.interface.api.dependencies import get_transition_to_fault
from app.interface.api.schemas import VehicleStatusUpdateIn, VehicleStatusUpdateOut

router = APIRouter(prefix="/api/v1", tags=["admin"])


@router.post(
    "/vehicles/{vehicle_id}/status",
    response_model=VehicleStatusUpdateOut,
)
async def update_vehicle_status(
    vehicle_id: str,
    body: VehicleStatusUpdateIn,
    transition_to_fault: TransitionToFault = Depends(get_transition_to_fault),
) -> VehicleStatusUpdateOut:
    if body.status != "fault":
        factory = get_session_factory()
        async with SqlAlchemyUnitOfWork(factory) as uow:
            await uow.snapshots.set_status_for_update(vehicle_id, body.status)
            await uow.commit()
        return VehicleStatusUpdateOut(vehicle_id=vehicle_id, idempotent=False)

    # Synthetic source_event_id keyed on the admin call (idempotent only within the same call).
    from uuid import uuid4

    source_event_id = uuid4()
    result = await transition_to_fault.execute(
        TransitionToFaultCommand(
            vehicle_id=vehicle_id,
            source_event_id=source_event_id,
            error_codes=tuple(body.error_codes),
            reason=body.reason,
        )
    )
    return VehicleStatusUpdateOut(
        vehicle_id=result.vehicle_id,
        maintenance_record_id=result.maintenance_record_id,
        cancelled_mission_id=result.cancelled_mission_id,
        idempotent=result.idempotent,
    )
