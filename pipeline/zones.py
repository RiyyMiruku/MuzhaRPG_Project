"""Zone slug helpers.

Zone vocabulary is now per-chapter and lives in
`story/chapters/<slug>/zones.json` (single source of truth). Orchestrators
trust the caller's slug — no hardcoded enum here.

Basic format check only: lowercase alphanumeric/underscore, or the sentinel
"*" meaning "cross-zone / shared".
"""
from __future__ import annotations

import re

_SLUG_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


def validate_zone(zone: str | None) -> None:
    if zone is None or zone == "*":
        return
    if not _SLUG_RE.match(zone):
        raise ValueError(
            f"invalid zone slug '{zone}'; expect lowercase snake_case or '*'"
        )


def parse_zones_csv(value: str | None) -> list[str]:
    """Split comma-separated zone slugs; validate each. Empty/None → []."""
    if not value:
        return []
    out: list[str] = []
    for raw in value.split(","):
        s = raw.strip()
        if not s:
            continue
        validate_zone(s)
        out.append(s)
    return out


def resolve_zone_tags(zones_csv: str | None, zone_legacy: str | None) -> list[str]:
    """Merge legacy --zone single value + new --zones csv; return tag strings.

    Returns ['zone:<slug>', ...] in input order, de-duplicated.
    """
    slugs: list[str] = []
    for s in parse_zones_csv(zones_csv):
        if s not in slugs:
            slugs.append(s)
    if zone_legacy:
        validate_zone(zone_legacy)
        if zone_legacy not in slugs:
            slugs.append(zone_legacy)
    return [f"zone:{s}" for s in slugs]
