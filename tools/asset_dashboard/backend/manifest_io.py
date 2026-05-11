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


def _stages_for(asset_type: AssetType, entry: dict) -> list[str]:
    if asset_type == "character" and entry.get("preset") == "npc":
        return CHARACTER_STAGES_STATIC
    return STAGE_ORDER[asset_type]


@dataclass
class AssetSummary:
    name: str
    asset_type: AssetType
    description: str | None
    tags: list[str]
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


def load_assets(manifest_path: Path) -> list[AssetSummary]:
    if not manifest_path.exists():
        return []
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    out: list[AssetSummary] = []
    for bucket, asset_type in _BUCKETS.items():
        section = raw.get(bucket) or {}
        for name, entry in section.items():
            tags = list(entry.get("tags") or [])
            stages = entry.get("stages") or {}
            completed: list[str] = list(stages.keys())
            all_stages = _stages_for(asset_type, entry)
            png_path = entry.get("game_png_path") or entry.get("local_path")
            out.append(AssetSummary(
                name=name,
                asset_type=asset_type,
                description=entry.get("description"),
                tags=tags,
                zone=_parse_tag(tags, "zone"),
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
