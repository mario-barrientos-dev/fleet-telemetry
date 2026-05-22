from __future__ import annotations

from uuid import UUID

import uuid_utils


class UUIDv7Generator:
    def next(self) -> UUID:
        return UUID(str(uuid_utils.uuid7()))
