# tools/asset_dashboard/backend/thumbnails.py
"""Pick a representative PNG to show as the asset thumbnail."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

AssetType = Literal["character", "tileset", "object"]


def resolve_thumbnail(
    repo_root: Path,
    asset_type: AssetType,
    name: str,
    entry: dict,
) -> Path | None:
    """Return the absolute path of a PNG to display as thumbnail, or None.

    Lookup rules:
      - character: <output>/characters/<name>/rotations/south.png
      - tileset:   <output>/tilesets/<name>/<name>_iso.png
      - object:    <output>/objects/<name>/<name>.png
    """
    pipeline_out = repo_root / "art_source" / "pipeline" / "output"
    if asset_type == "character":
        candidate = pipeline_out / "characters" / name / "rotations" / "south.png"
    elif asset_type == "tileset":
        candidate = pipeline_out / "tilesets" / name / f"{name}_iso.png"
    elif asset_type == "object":
        candidate = pipeline_out / "objects" / name / f"{name}.png"
    else:
        return None
    return candidate if candidate.exists() else None
