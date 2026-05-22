from __future__ import annotations

from app.zones import ZONES, ZONES_SET


def test_zones_are_exactly_twenty() -> None:
    assert len(ZONES) == 20


def test_zones_are_unique() -> None:
    assert len(ZONES) == len(ZONES_SET)


def test_zones_set_matches_tuple() -> None:
    assert frozenset(ZONES) == ZONES_SET
