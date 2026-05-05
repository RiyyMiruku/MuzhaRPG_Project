#!/usr/bin/env python3
"""Compile art-pipeline character output into a single spritesheet + atlas JSON.

Reads:  art_source/pipeline/output/characters/<name>/animations/<action>/<direction>/frame_*.png
Writes: art_source/pipeline/output/characters/<name>/spritesheet/<name>.png
        art_source/pipeline/output/characters/<name>/spritesheet/<name>.json

Per-character output (no shared atlas_config). Orchestrator's import_to_godot
stage copies these into game/assets/textures/characters/.

Usage:
    uv run python scripts/generate_spritesheet.py --character-dir <path>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from PIL import Image

FRAME_SIZE = (92, 92)
DIRECTION_ORDER = ["south", "east", "north", "west"]
ACTION_ORDER = ["idle", "walk"]


def _natural_key(p: Path) -> tuple:
    import re
    return tuple(int(s) if s.isdigit() else s for s in re.split(r"(\d+)", p.stem))


def _collect_rows(char_dir: Path) -> list[tuple[str, str, list[Path]]]:
    """Return [(action, direction, sorted_frame_paths), ...] in stable order."""
    anim_root = char_dir / "animations"
    rows: list[tuple[str, str, list[Path]]] = []
    actions = sorted(
        (d for d in anim_root.iterdir() if d.is_dir()),
        key=lambda d: (ACTION_ORDER.index(d.name) if d.name in ACTION_ORDER else 99, d.name),
    ) if anim_root.is_dir() else []

    for action_dir in actions:
        for direction in DIRECTION_ORDER:
            dir_path = action_dir / direction
            if not dir_path.is_dir():
                continue
            frames = sorted(dir_path.glob("frame_*.png"), key=_natural_key)
            if frames:
                rows.append((action_dir.name, direction, frames))
    return rows


def compile_character(char_dir: Path) -> tuple[Path, Path]:
    rows = _collect_rows(char_dir)
    if not rows:
        raise SystemExit(f"no animations found under {char_dir}/animations/")

    max_frames = max(len(r[2]) for r in rows)
    width = max_frames * FRAME_SIZE[0]
    height = len(rows) * FRAME_SIZE[1]

    sheet = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for row_idx, (_action, _direction, frames) in enumerate(rows):
        for col_idx, frame_path in enumerate(frames):
            with Image.open(frame_path) as f:
                sheet.paste(f.convert("RGBA"), (col_idx * FRAME_SIZE[0], row_idx * FRAME_SIZE[1]))

    out_dir = char_dir / "spritesheet"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = char_dir.name
    png_path = out_dir / f"{name}.png"
    json_path = out_dir / f"{name}.json"

    sheet.save(png_path, "PNG", compress_level=6)

    atlas = {
        "character_name": name,
        "frame_size": list(FRAME_SIZE),
        "animations": {
            f"{action}_{direction}": {
                "row": row_idx,
                "start": 0,
                "end": len(frames),
                "fps": 6.0,
                "loop": True,
            }
            for row_idx, (action, direction, frames) in enumerate(rows)
        },
    }
    json_path.write_text(json.dumps(atlas, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[ok] {name}: {len(rows)} rows × {max_frames} cols → {png_path.name}")
    return png_path, json_path


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--character-dir", type=Path, required=True,
                   help="path to art_source/pipeline/output/characters/<name>/")
    args = p.parse_args()
    compile_character(args.character_dir.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
