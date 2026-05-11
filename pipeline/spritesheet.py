"""Incremental spritesheet writer for art-pipeline characters.

The sheet PNG + sister JSON under `art_source/characters/<name>/spritesheet/`
is the single source of truth for character animations — Pixellab frames are
pasted directly into the sheet, never saved as per-frame PNGs.

Public API:
    load_or_init_sheet(char_dir)       — open existing or create placeholder
    write_animation_frames(...)        — paste a row, growing the sheet as needed
    save_sheet(char_dir, sheet, atlas) — write PNG + JSON atomically
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

FRAME_SIZE: tuple[int, int] = (92, 92)


def _sheet_paths(char_dir: Path) -> tuple[Path, Path]:
    name = char_dir.name
    out_dir = char_dir / "spritesheet"
    return out_dir / f"{name}.png", out_dir / f"{name}.json"


def load_or_init_sheet(char_dir: Path) -> tuple[Image.Image, dict]:
    """Open existing spritesheet + atlas, or return a tiny empty pair to
    grow on first write. Rows are assigned lazily in write_animation_frames."""
    png_path, json_path = _sheet_paths(char_dir)
    if png_path.exists() and json_path.exists():
        atlas = json.loads(json_path.read_text(encoding="utf-8"))
        sheet = Image.open(png_path).convert("RGBA")
        return sheet, atlas
    atlas = {
        "character_name": char_dir.name,
        "frame_size": list(FRAME_SIZE),
        "animations": {},
    }
    return Image.new("RGBA", FRAME_SIZE, (0, 0, 0, 0)), atlas


def write_animation_frames(
    sheet: Image.Image,
    atlas: dict,
    action: str,
    direction: str,
    frames: list[Image.Image],
    *,
    fps: float = 6.0,
    loop: bool = True,
) -> tuple[Image.Image, dict]:
    """Paste `frames` into the sheet at the row for (action, direction),
    growing the sheet if needed. Returns the (possibly new) sheet + atlas.

    Row index is taken from atlas['animations'][f'{action}_{direction}'].row
    when present; otherwise a fresh row is appended at the end. Column count
    matches len(frames); sheet width grows to fit if the new row is longer
    than the existing max.
    """
    if not frames:
        raise ValueError(f"no frames provided for {action}/{direction}")
    fw, fh = atlas.get("frame_size") or FRAME_SIZE
    animations = atlas.setdefault("animations", {})
    key = f"{action}_{direction}"
    entry = animations.get(key)
    row = entry["row"] if entry and isinstance(entry.get("row"), int) else len(animations)

    need_w = max(sheet.size[0], len(frames) * fw)
    need_h = max(sheet.size[1], (row + 1) * fh)
    if (need_w, need_h) != sheet.size:
        grown = Image.new("RGBA", (need_w, need_h), (0, 0, 0, 0))
        grown.paste(sheet, (0, 0))
        sheet = grown

    # Clear the row band so a shorter regen wipes trailing stale frames.
    ImageDraw.Draw(sheet).rectangle(
        [(0, row * fh), (sheet.size[0], (row + 1) * fh)],
        fill=(0, 0, 0, 0),
    )
    for col_idx, frame in enumerate(frames):
        f = frame if frame.mode == "RGBA" else frame.convert("RGBA")
        if f.size != (fw, fh):
            f = f.resize((fw, fh), Image.Resampling.NEAREST)
        sheet.paste(f, (col_idx * fw, row * fh), f)

    animations[key] = {
        "row": row,
        "start": 0,
        "end": len(frames),
        "fps": fps,
        "loop": loop,
    }
    return sheet, atlas


def save_sheet(char_dir: Path, sheet: Image.Image, atlas: dict) -> tuple[Path, Path]:
    """Write sheet PNG + atlas JSON."""
    png_path, json_path = _sheet_paths(char_dir)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(png_path, "PNG", compress_level=6)
    json_path.write_text(json.dumps(atlas, indent=2, ensure_ascii=False), encoding="utf-8")
    return png_path, json_path
