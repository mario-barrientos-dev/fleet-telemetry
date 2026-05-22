from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.infrastructure.db.session import get_session_factory
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.interface.api.schemas import ZoneCountOut, ZoneCountsOut
from app.zones import ZONES

router = APIRouter(prefix="/api/v1", tags=["zones"])


@router.get("/zones/counts", response_model=ZoneCountsOut)
async def zone_counts() -> ZoneCountsOut:
    factory = get_session_factory()
    async with SqlAlchemyUnitOfWork(factory) as uow:
        counts = await uow.zones.counts()

    data = [ZoneCountOut(zone_id=zid, entry_count=counts.get(zid, 0)) for zid in ZONES]
    return ZoneCountsOut(data=data, as_of=datetime.now(UTC))
