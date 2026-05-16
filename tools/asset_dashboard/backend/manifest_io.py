# tools/asset_dashboard/backend/manifest_io.py
"""Read manifest.json and project it as flat asset summaries for the dashboard."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Literal

AssetType = Literal["character", "tileset", "object"]

STAGE_ORDER: dict[AssetType, list[str]] = {
    "character": [  # moving NPC / player (preset="player")
        "generate_8dir_base",
        "add_idle_animation",
        "add_walk_animation",
        "compile_spritesheet",
        "import_to_godot",
    ],
    "tileset": [
        "generate_atlas",
        "iso_project",
        "verify_in_godot",
        "import_to_godot",
    ],
    "object": [
        "generate_object",
        "chroma_key",
        "import_to_godot",
    ],
}

# Static NPC variant (preset="npc"): no walk stage, and the rotation stage
# is named differently in npc_static.py (it generates 4 OR 8 directions but
# the stage key is always generate_4dir_base).
CHARACTER_STAGES_STATIC: list[str] = [
    "generate_4dir_base",
    "add_idle_animation",
    "compile_spritesheet",
    "import_to_godot",
]

# v2 pipeline (file-per-asset + async stages). Same stage list for moving + static;
# animate_walk no-op-completes for 4-dir chars (still recorded as 'completed')
# so progress counter reflects "all stages ran" uniformly.
CHARACTER_STAGES_V2: list[str] = [
    "generate_rotations",
    "animate_idle",
    "animate_walk",
    "import_to_godot",
]


def _stages_for(asset_type: AssetType, entry: dict) -> list[str]:
    is_v2 = int(entry.get("pipeline_version", 1)) >= 2
    if asset_type == "character":
        if is_v2:
            return CHARACTER_STAGES_V2
        if entry.get("preset") == "npc":
            return CHARACTER_STAGES_STATIC
    return STAGE_ORDER[asset_type]


@dataclass
class AssetSummary:
    name: str
    asset_type: AssetType
    description: str | None
    tags: list[str]
    # All zone:* tag values (without prefix). An asset can belong to multiple
    # zones; "*" sentinel means cross-zone / shared.
    zones: list[str]
    # Legacy single-value mirror — first entry of `zones`, or None when empty.
    # Kept so older frontend code keeps compiling during the migration.
    zone: str | None
    category: str | None
    chapter: str | None
    completed_stages: list[str]
    all_stages: list[str]
    prompts: dict[str, str]
    png_path: str | None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["progress"] = f"{len(self.completed_stages)}/{len(self.all_stages)}"
        return d


_BUCKETS: dict[str, AssetType] = {
    "characters": "character",
    "tilesets": "tileset",
    "objects": "object",
}


def _parse_tag(tags: list[str], key: str) -> str | None:
    prefix = f"{key}:"
    for t in tags:
        if t.startswith(prefix):
            return t[len(prefix):]
    return None


def _parse_tags_multi(tags: list[str], key: str) -> list[str]:
    """Return all values for repeated `key:value` tags, in order, de-duplicated."""
    prefix = f"{key}:"
    out: list[str] = []
    for t in tags:
        if t.startswith(prefix):
            v = t[len(prefix):]
            if v and v not in out:
                out.append(v)
    return out


def load_assets(manifest_data: dict | Path) -> list[AssetSummary]:
    """Project manifest into flat asset summaries for the dashboard.

    Accepts either:
      - a dict (the modern path: pass `pipeline_manifest.load()`)
      - a Path (legacy: aggregated manifest.json file). Kept for tests +
        any caller still using the v1 file directly.
    """
    if isinstance(manifest_data, Path):
        if not manifest_data.exists():
            return []
        raw = json.loads(manifest_data.read_text(encoding="utf-8"))
    else:
        raw = manifest_data
    out: list[AssetSummary] = []
    for bucket, asset_type in _BUCKETS.items():
        section = raw.get(bucket) or {}
        for name, entry in section.items():
            tags = list(entry.get("tags") or [])
            stages = entry.get("stages") or {}
            # A stage counts as 'completed' if v2-style status=='completed',
            # OR (legacy: status field absent but completed_at recorded).
            completed: list[str] = [
                n for n, st in stages.items()
                if isinstance(st, dict) and (
                    st.get("status") == "completed"
                    or ("status" not in st and st.get("completed_at"))
                )
            ]
            all_stages = _stages_for(asset_type, entry)
            png_path = entry.get("game_png_path") or entry.get("local_path")
            zone_list = _parse_tags_multi(tags, "zone")
            out.append(AssetSummary(
                name=name,
                asset_type=asset_type,
                description=entry.get("description"),
                tags=tags,
                zones=zone_list,
                zone=(zone_list[0] if zone_list else None),
                category=_parse_tag(tags, "category"),
                chapter=_parse_tag(tags, "chapter"),
                completed_stages=completed,
                all_stages=all_stages,
                prompts=dict(entry.get("prompts") or {}),
                png_path=png_path,
                extra={
                    "character_id": entry.get("character_id"),
                    "directions": entry.get("directions"),
                    "kind": entry.get("kind"),
                },
            ))
    return out
