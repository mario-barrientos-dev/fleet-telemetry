"""Per-vehicle asyncio locks.

The detector is stateful (it compares current with previous event from the
same vehicle). Two concurrent ingests for the same vehicle would race on the
in-memory `previous` cache and could produce inconsistent anomalies. Locks
serialise per-vehicle while preserving full parallelism across distinct
vehicles. Single-process only; ADR §3 (scale) sketches the partition-by-vehicle
path for multi-process deployments.
"""

from __future__ import annotations

import asyncio


class VehicleLockMap:
    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    async def acquire(self, vehicle_id: str) -> asyncio.Lock:
        if vehicle_id in self._locks:
            return self._locks[vehicle_id]
        async with self._guard:
            if vehicle_id not in self._locks:
                self._locks[vehicle_id] = asyncio.Lock()
            return self._locks[vehicle_id]
