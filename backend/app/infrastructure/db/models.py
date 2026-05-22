from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base for all ORM models. Concrete tables are added in Fase 1."""
