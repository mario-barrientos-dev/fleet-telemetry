from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.db.repositories import (
    SqlAnomalyRepository,
    SqlMaintenanceRepository,
    SqlMissionRepository,
    SqlTelemetryRepository,
    SqlVehicleSnapshotRepository,
    SqlZoneEntryRepository,
)


class SqlAlchemyUnitOfWork:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        isolation: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._isolation = isolation
        self._session: AsyncSession | None = None
        self.telemetry: SqlTelemetryRepository = None  # type: ignore[assignment]
        self.snapshots: SqlVehicleSnapshotRepository = None  # type: ignore[assignment]
        self.zones: SqlZoneEntryRepository = None  # type: ignore[assignment]
        self.missions: SqlMissionRepository = None  # type: ignore[assignment]
        self.maintenance: SqlMaintenanceRepository = None  # type: ignore[assignment]
        self.anomalies: SqlAnomalyRepository = None  # type: ignore[assignment]

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_factory()
        if self._isolation:
            await self._session.connection(execution_options={"isolation_level": self._isolation})
        self.telemetry = SqlTelemetryRepository(self._session)
        self.snapshots = SqlVehicleSnapshotRepository(self._session)
        self.zones = SqlZoneEntryRepository(self._session)
        self.missions = SqlMissionRepository(self._session)
        self.maintenance = SqlMaintenanceRepository(self._session)
        self.anomalies = SqlAnomalyRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self.rollback()
        finally:
            if self._session is not None:
                await self._session.close()
                self._session = None

    async def commit(self) -> None:
        assert self._session is not None
        await self._session.commit()

    async def rollback(self) -> None:
        assert self._session is not None
        await self._session.rollback()

    @property
    def session(self) -> AsyncSession:
        assert self._session is not None
        return self._session
