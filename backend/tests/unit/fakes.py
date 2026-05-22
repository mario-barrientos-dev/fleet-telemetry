"""Test doubles for ports defined in app.domain.ports."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    @classmethod
    def at(cls, iso: str) -> FakeClock:
        return cls(datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(UTC))

    def now(self) -> datetime:
        return self._now

    def advance(self, *, seconds: float = 0, hours: float = 0) -> None:
        self._now = self._now + timedelta(seconds=seconds, hours=hours)


class SequentialIdGenerator:
    def __init__(self, start: int = 1) -> None:
        self._n = start

    def next(self) -> UUID:
        out = UUID(int=self._n)
        self._n += 1
        return out
