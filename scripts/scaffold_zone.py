"""Scaffold a Godot zone scene for autotile-based ground painting.

For each zone with autotile_*.png in game/assets/textures/environment/tilesets/<zone>/:
  1. Generate game/src/maps/tilesets/<zone>_terrain.tres (atlas source per PNG, no Terrain bits)
  2. Patch game/src/maps/zones/zone_<zone>.tscn:
     - Add TileMapLayer_Ground node (sibling of YSortRoot, drawn beneath it)
     - Wire its tile_set property to the .tres above
  3. Leave the Ground ColorRect placeholder alone — artist deletes it after painting.

Idempotent: running twice does nothing if scaffold already exists.

The Terrain Set + peering bits step is intentionally left to the Godot editor
(visual; very fragile to author by hand). After this script, in Godot:
  - Select TileMapLayer_Ground -> Inspector shows attached TileSet
  - Open TileSet editor -> Terrain Sets tab -> add Terrain Set with 2 terrains
  - Tiles tab -> paint terrain bits onto the 4 sub-tiles
  - TileMap panel -> Terrains tab -> brush onto the scene

Usage:
  python scripts/scaffold_zone.py              # scaffold all zones with autotile PNGs
  python scripts/scaffold_zone.py nccu market  # only specific zones
  python scripts/scaffold_zone.py --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TILESETS_PNG = ROOT / "game/assets/textures/environment/tilesets"
TILESETS_TRES = ROOT / "game/src/maps/tilesets"
ZONES_DIR = ROOT / "game/src/maps/zones"
TILE_SIZE = 16


def list_zones() -> list[str]:
    return sorted(d.name for d in TILESETS_PNG.iterdir() if d.is_dir() and any(d.glob("autotile_*.png")))


def write_tileset_tres(zone: str, pngs: list[Path], dry_run: bool) -> Path:
    tres_path = TILESETS_TRES / f"{zone}_terrain.tres"
    rel_pngs = [
        "res://" + str(p.relative_to(ROOT / "game")).replace("\\", "/")
        for p in pngs
    ]

    parts: list[str] = []
    load_steps = 1 + len(pngs) * 2  # ext_resource + sub_resource per png + 1 for resource header
    parts.append(f'[gd_resource type="TileSet" load_steps={load_steps} format=3]\n')
    for i, rel in enumerate(rel_pngs):
        parts.append(f'[ext_resource type="Texture2D" path="{rel}" id="{i+1}_tex"]')
    parts.append("")
    for i, _ in enumerate(rel_pngs):
        # Pixellab autotile = 64x64 with 4 tiles (2x2) of 16x16
        parts.append(f'[sub_resource type="TileSetAtlasSource" id="atlas_{i+1}"]')
        parts.append(f'texture = ExtResource("{i+1}_tex")')
        parts.append(f'texture_region_size = Vector2i({TILE_SIZE}, {TILE_SIZE})')
        for ax in (0, 1):
            for ay in (0, 1):
                parts.append(f'{ax}:{ay}/0 = 0')
        parts.append("")
    parts.append("[resource]")
    parts.append(f'tile_size = Vector2i({TILE_SIZE}, {TILE_SIZE})')
    for i in range(len(pngs)):
        parts.append(f'sources/{i} = SubResource("atlas_{i+1}")')
    parts.append("")

    content = "\n".join(parts)
    if not dry_run:
        TILESETS_TRES.mkdir(parents=True, exist_ok=True)
        tres_path.write_text(content, encoding="utf-8")
    return tres_path


def patch_zone_scene(zone: str, tres_path: Path, dry_run: bool) -> tuple[bool, str]:
    """Insert TileMapLayer_Ground node into zone scene. Returns (changed, reason)."""
    scene_path = ZONES_DIR / f"zone_{zone}.tscn"
    if not scene_path.exists():
        return False, f"scene not found: {scene_path}"

    text = scene_path.read_text(encoding="utf-8")
    if 'name="TileMapLayer_Ground"' in text:
        return False, "already scaffolded"

    rel_tres = "res://" + str(tres_path.relative_to(ROOT / "game")).replace("\\", "/")

    # 1. Find the last ext_resource line and append new one after it.
    ext_pattern = re.compile(r'(\[ext_resource [^\]]+\]\n)(?!\[ext_resource)', re.MULTILINE)
    matches = list(re.finditer(r'\[ext_resource [^\]]+\]\n', text))
    if not matches:
        return False, "no ext_resource block found in scene"
    last_ext = matches[-1]
    ext_line = f'[ext_resource type="TileSet" path="{rel_tres}" id="ts_{zone}_ground"]\n'
    text = text[:last_ext.end()] + ext_line + text[last_ext.end():]

    # 2. Insert TileMapLayer_Ground node before YSortRoot node block.
    ysort_match = re.search(r'\[node name="YSortRoot"', text)
    if not ysort_match:
        return False, "no YSortRoot node found"
    insert_at = ysort_match.start()
    node_block = (
        '[node name="TileMapLayer_Ground" type="TileMapLayer" parent="."]\n'
        f'tile_set = ExtResource("ts_{zone}_ground")\n'
        '\n'
    )
    text = text[:insert_at] + node_block + text[insert_at:]

    # 3. Bump load_steps in [gd_scene ...] header.
    def bump(m: re.Match) -> str:
        n = int(m.group(1)) + 1
        return f'load_steps={n}'
    text = re.sub(r'load_steps=(\d+)', bump, text, count=1)

    if not dry_run:
        scene_path.write_text(text, encoding="utf-8")
    return True, "scaffolded"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("zones", nargs="*", help="zone names; default = all zones with autotile PNGs")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    available = list_zones()
    targets = args.zones or available
    unknown = [z for z in targets if z not in available]
    if unknown:
        print(f"WARNING: no autotile PNG found for zone(s): {', '.join(unknown)}", file=sys.stderr)
        targets = [z for z in targets if z in available]

    if not targets:
        print("nothing to scaffold (no autotile PNGs in any zone).", file=sys.stderr)
        return 1

    for zone in targets:
        pngs = sorted((TILESETS_PNG / zone).glob("autotile_*.png"))
        tres_path = write_tileset_tres(zone, pngs, args.dry_run)
        changed, reason = patch_zone_scene(zone, tres_path, args.dry_run)
        rel_tres = tres_path.relative_to(ROOT)
        rel_scene = (ZONES_DIR / f"zone_{zone}.tscn").relative_to(ROOT)
        action = "would write" if args.dry_run else "wrote"
        print(f"[{zone}] {action} {rel_tres}  ({len(pngs)} autotile png)")
        print(f"[{zone}] zone scene: {rel_scene} -> {reason}")

    if args.dry_run:
        print("\n(dry-run, nothing changed)")
    else:
        print("\nDone. Open Godot, Ctrl+Shift+R to rescan, then:")
        print("  - Select TileMapLayer_Ground in zone scene")
        print("  - Open the attached TileSet -> Terrain Sets tab -> add terrains + paint peering bits")
        print("  - TileMap panel -> Terrains tab -> brush the ground")
        print("  - Delete the placeholder 'Ground' ColorRect once you have terrain painted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
