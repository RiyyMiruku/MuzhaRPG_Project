"""Single source of truth for canonical zone names."""
from __future__ import annotations

ZONES: list[str] = ["market", "nccu", "riverside", "zhinan", "shared", "test"]


def validate_zone(zone: str | None) -> None:
    if zone is not None and zone not in ZONES:
        raise ValueError(f"unknown zone '{zone}';valid: {ZONES}")
