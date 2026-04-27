"""Scaffold a Godot zone scene for autotile-based ground painting.

For each zone with autotile_*.png in game/assets/textures/environment/tilesets/<zone>/:
  1. Generate game/src/maps/tilesets/<zone>_terrain.tres with:
     - One TileSetAtlasSource per PNG (Pixellab 4x4 = 16 tiles of 16x16)
     - Full Match-Corners peering bits per PIXELLAB_LAYOUT (no editor work needed)
     - Terrain Set per atlas with terrain_0/terrain_1 named from filename
  2. Patch game/src/maps/zones/zone_<zone>.tscn:
     - Add TileMapLayer_Ground node (sibling of YSortRoot, drawn beneath it)
     - Wire its tile_set property to the .tres above
  3. Leave the Ground ColorRect placeholder alone — artist deletes it after painting.

Skips overwriting .tres files that already have `terrain_set_0/mode` (manually
edited). Use --force to overwrite anyway.

After this script, in Godot:
  - Ctrl+Shift+R to rescan
  - Select TileMapLayer_Ground -> TileMap panel -> Terrains tab -> brush directly
  - If terrain visually inverted (e.g., painting "grass" produces asphalt),
    swap terrain_0/terrain_1 names+colors in the .tres for that set.

Usage:
  python scripts/scaffold_zone.py              # scaffold all zones with autotile PNGs
  python scripts/scaffold_zone.py nccu market  # only specific zones
  python scripts/scaffold_zone.py --force      # overwrite manually-edited .tres
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

# Pixellab Tilesets 4x4 PNG layout: position (col,row) -> wang corner bitmask
# (bit 0=TL, 1=TR, 2=BL, 3=BR; bit set = upper/inner terrain corner)
# Derived empirically from autotile_grass_asphalt.png (market) where
# (2,1) = pure outer/lower (bitmask 0), (0,3) = pure inner/upper (bitmask 15).
PIXELLAB_LAYOUT = {
    (0, 0): 11, (1, 0): 5,  (2, 0): 2,  (3, 0): 3,
    (0, 1): 6,  (1, 1): 1,  (2, 1): 0,  (3, 1): 8,
    (0, 2): 13, (1, 2): 12, (2, 2): 4,  (3, 2): 10,
    (0, 3): 15, (1, 3): 7,  (2, 3): 9,  (3, 3): 14,
}

# Default palette colors for known terrain names. Unknown names fall back to grey.
TERRAIN_COLORS: dict[str, tuple[float, float, float]] = {
    "dirt":     (0.55, 0.4, 0.25),
    "stone":    (0.6, 0.6, 0.6),
    "grass":    (0.25, 0.75, 0.3),
    "asphalt":  (0.35, 0.35, 0.4),
    "water":    (0.3, 0.5, 0.85),
    "concrete": (0.65, 0.65, 0.65),
    "path":     (0.7, 0.55, 0.4),
    "sand":     (0.9, 0.85, 0.5),
    "mud":      (0.4, 0.3, 0.2),
    "brick":    (0.65, 0.3, 0.25),
}


def parse_terrain_names(png: Path) -> tuple[str, str]:
    """Filename `autotile_<lower>_<upper>.png` -> (lower, upper)."""
    stem = png.stem  # autotile_grass_asphalt
    parts = stem.split("_", 2)  # ['autotile', 'grass', 'asphalt']
    if len(parts) >= 3 and parts[0] == "autotile":
        return parts[1], parts[2]
    return "lower", "upper"


def color_str(name: str) -> str:
    r, g, b = TERRAIN_COLORS.get(name, (0.5, 0.5, 0.5))
    return f"Color({r}, {g}, {b}, 1)"


def list_zones() -> list[str]:
    return sorted(d.name for d in TILESETS_PNG.iterdir() if d.is_dir() and any(d.glob("autotile_*.png")))


def write_tileset_tres(zone: str, pngs: list[Path], dry_run: bool, force: bool) -> tuple[Path, str]:
    tres_path = TILESETS_TRES / f"{zone}_terrain.tres"
    if tres_path.exists() and not force:
        existing = tres_path.read_text(encoding="utf-8")
        if "terrain_set_0/mode" in existing:
            return tres_path, "skipped (already has Terrain Set; use --force to overwrite)"
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

    # Atlas sources: each PNG is a Pixellab 4x4 = 16-tile autotile.
    # Each tile gets full Match-Corners peering bits per PIXELLAB_LAYOUT.
    for i, _ in enumerate(rel_pngs):
        parts.append(f'[sub_resource type="TileSetAtlasSource" id="atlas_{i+1}"]')
        parts.append(f'texture = ExtResource("{i+1}_tex")')
        parts.append(f'texture_region_size = Vector2i({TILE_SIZE}, {TILE_SIZE})')
        for (col, row), bm in PIXELLAB_LAYOUT.items():
            tl = 1 if bm & 1 else 0
            tr = 1 if bm & 2 else 0
            bl = 1 if bm & 4 else 0
            br = 1 if bm & 8 else 0
            popcount = tl + tr + bl + br
            base_terrain = 1 if popcount >= 3 else 0
            parts.append(f'{col}:{row}/0 = 0')
            parts.append(f'{col}:{row}/0/terrain_set = {i}')
            parts.append(f'{col}:{row}/0/terrain = {base_terrain}')
            parts.append(f'{col}:{row}/0/terrains_peering_bit/top_left_corner = {tl}')
            parts.append(f'{col}:{row}/0/terrains_peering_bit/top_right_corner = {tr}')
            parts.append(f'{col}:{row}/0/terrains_peering_bit/bottom_left_corner = {bl}')
            parts.append(f'{col}:{row}/0/terrains_peering_bit/bottom_right_corner = {br}')
        parts.append("")

    parts.append("[resource]")
    parts.append(f'tile_size = Vector2i({TILE_SIZE}, {TILE_SIZE})')
    # Terrain Set definitions: one set per atlas, names derived from filename.
    # NOTE: filename order = `<lower>_<upper>`, so terrain 0 = lower (background),
    # terrain 1 = upper (foreground/path). If visually inverted in Godot, swap
    # terrain_0/terrain_1 names+colors for the affected set.
    for i, png in enumerate(pngs):
        lower, upper = parse_terrain_names(png)
        parts.append(f'terrain_set_{i}/mode = 1')  # 1 = Match Corners
        parts.append(f'terrain_set_{i}/terrain_0/name = "{lower}"')
        parts.append(f'terrain_set_{i}/terrain_0/color = {color_str(lower)}')
        parts.append(f'terrain_set_{i}/terrain_1/name = "{upper}"')
        parts.append(f'terrain_set_{i}/terrain_1/color = {color_str(upper)}')
    for i in range(len(pngs)):
        parts.append(f'sources/{i} = SubResource("atlas_{i+1}")')
    parts.append("")

    content = "\n".join(parts)
    if not dry_run:
        TILESETS_TRES.mkdir(parents=True, exist_ok=True)
        tres_path.write_text(content, encoding="utf-8")
    return tres_path, "wrote"


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
    p.add_argument("--force", action="store_true", help="overwrite .tres even if it has terrain_set_0/mode")
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
        tres_path, tres_action = write_tileset_tres(zone, pngs, args.dry_run, args.force)
        changed, reason = patch_zone_scene(zone, tres_path, args.dry_run)
        rel_tres = tres_path.relative_to(ROOT)
        rel_scene = (ZONES_DIR / f"zone_{zone}.tscn").relative_to(ROOT)
        action = ("would " + tres_action) if args.dry_run else tres_action
        print(f"[{zone}] {action}: {rel_tres}  ({len(pngs)} autotile png)")
        print(f"[{zone}] zone scene: {rel_scene} -> {reason}")

    if args.dry_run:
        print("\n(dry-run, nothing changed)")
    else:
        print("\nDone. Open Godot, Ctrl+Shift+R to rescan, then:")
        print("  - Select TileMapLayer_Ground in zone scene")
        print("  - TileMap panel -> Terrains tab -> brush the ground directly")
        print("  - If a terrain visually paints inverted, swap terrain_0/terrain_1 names in the .tres")
        print("  - Delete the placeholder 'Ground' ColorRect once you have terrain painted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
