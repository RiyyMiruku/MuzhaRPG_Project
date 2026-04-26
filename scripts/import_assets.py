"""Import raw art assets from temp/ into the project structure.

Workflow (artist + AI hybrid):
  1. Artist drops new asset folders into temp/ (any structure).
  2. AI/artist writes a TOML manifest describing each folder's intent.
  3. Run:  python scripts/import_assets.py temp/import.toml
  4. Script renames + moves PNGs into the correct project folders, and
     generates Godot .tscn prop scenes (for prop entries).

The manifest declares the *human judgment* part (category, collision intent);
the script handles the mechanical part (rename, move, generate .tscn).

Manifest format (TOML):

  [[items]]
  folder = "temp/tilesets/market/red_lantern"   # source folder of tile*.png
  type = "prop"                                  # "prop" | "autotile"
  category = "urban"                             # "urban" | "nature"  (prop only)
  zone = "market"                                # required for autotile
  has_collision = false
  collision = "none"                             # see COLLISION_PRESETS below

CLI:
  python scripts/import_assets.py <manifest.toml>
  python scripts/import_assets.py --init temp/   # scaffold a manifest from temp/
  python scripts/import_assets.py --dry-run <manifest.toml>
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PROPS_DIR = ROOT / "game/assets/textures/environment/props"
TILESETS_DIR = ROOT / "game/assets/textures/environment/tilesets"
PROP_SCENES_DIR = ROOT / "game/src/maps/props"

COLLISION_PRESETS = {
    "none": None,
    "bottom_16x8": (16, 8),
    "bottom_16x16": (16, 16),
    "full": "full",
}

UID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


@dataclass
class Item:
    folder: Path
    type: str
    category: str | None
    zone: str | None
    has_collision: bool
    collision: str

    @property
    def name(self) -> str:
        return self.folder.name


def godot_uid(seed: str) -> str:
    h = hashlib.sha1(seed.encode()).digest()
    n = int.from_bytes(h[:8], "big")
    return "uid://c" + "".join(UID_ALPHABET[(n >> (i * 5)) % 36] for i in range(13))


def parse_collision(spec: str) -> tuple[float, float] | str | None:
    if spec in COLLISION_PRESETS:
        return COLLISION_PRESETS[spec]
    if "x" in spec:
        try:
            w, h = spec.lower().split("x")
            return (float(w), float(h))
        except ValueError:
            pass
    raise ValueError(f"unknown collision spec: {spec!r}")


def collision_for(png_w: int, png_h: int, spec: str) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Return (size, position) of RectangleShape2D, or None for no collider."""
    parsed = parse_collision(spec)
    if parsed is None:
        return None
    if parsed == "full":
        return ((png_w, png_h), (0.0, -png_h / 2.0))
    w, h = parsed
    return ((w, h), (0.0, -h / 2.0))


def load_manifest(path: Path) -> list[Item]:
    with path.open("rb") as f:
        data = tomllib.load(f)
    items: list[Item] = []
    for entry in data.get("items", []):
        folder = (ROOT / entry["folder"]).resolve()
        if not folder.is_dir():
            raise FileNotFoundError(f"manifest folder not found: {folder}")
        items.append(Item(
            folder=folder,
            type=entry["type"],
            category=entry.get("category"),
            zone=entry.get("zone"),
            has_collision=bool(entry.get("has_collision", True)),
            collision=entry.get("collision", "full"),
        ))
    return items


def warn_unlisted(manifest_path: Path, items: list[Item]) -> None:
    """Fail loud if temp/ contains folders not listed in the manifest."""
    listed = {it.folder for it in items}
    temp_root = ROOT / "temp"
    if not temp_root.is_dir():
        return
    found_unlisted: list[Path] = []
    for d in temp_root.rglob("*"):
        if not d.is_dir():
            continue
        if not any(d.glob("*.png")):
            continue
        if d not in listed:
            found_unlisted.append(d)
    if found_unlisted:
        print("WARNING: these temp/ folders contain PNGs but are NOT in the manifest:", file=sys.stderr)
        for p in found_unlisted:
            print(f"  - {p.relative_to(ROOT)}", file=sys.stderr)
        print("Add them to the manifest or delete the folder. Continuing with listed items.", file=sys.stderr)


def import_prop(item: Item, dry_run: bool) -> list[str]:
    if item.category not in {"urban", "nature"}:
        raise ValueError(f"{item.name}: prop requires category=urban|nature")
    png_dest = PROPS_DIR / item.category
    tscn_dest = PROP_SCENES_DIR / item.category
    if not dry_run:
        png_dest.mkdir(parents=True, exist_ok=True)
        tscn_dest.mkdir(parents=True, exist_ok=True)

    log: list[str] = []
    def natural_key(p: Path) -> tuple:
        import re
        return tuple(int(s) if s.isdigit() else s for s in re.split(r"(\d+)", p.stem))

    pngs = sorted(item.folder.glob("tile*.png"), key=natural_key)
    if not pngs:
        pngs = sorted(item.folder.glob("*.png"), key=natural_key)
    n = len(pngs)
    pad = max(2, len(str(n)))

    for i, src in enumerate(pngs, start=1):
        new_name = f"{item.name}_{i:0{pad}d}"
        png_path = png_dest / f"{new_name}.png"
        tscn_path = tscn_dest / f"{new_name}.tscn"
        log.append(f"  png: {src.relative_to(ROOT)} -> {png_path.relative_to(ROOT)}")
        log.append(f"  tscn: {tscn_path.relative_to(ROOT)}")
        if dry_run:
            continue
        shutil.move(str(src), png_path)
        write_prop_tscn(tscn_path, png_path, item)

    if not dry_run:
        try:
            item.folder.rmdir()
        except OSError:
            pass
    return log


def import_autotile(item: Item, dry_run: bool) -> list[str]:
    if not item.zone:
        raise ValueError(f"{item.name}: autotile requires zone=...")
    dest = TILESETS_DIR / item.zone
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    log: list[str] = []
    pngs = sorted(item.folder.glob("*.png"))
    for src in pngs:
        # autotile keeps original filename if it already follows the convention,
        # otherwise prefix with folder name
        target_name = src.name if src.name.startswith("autotile_") else f"autotile_{item.name}.png"
        out = dest / target_name
        log.append(f"  png: {src.relative_to(ROOT)} -> {out.relative_to(ROOT)}")
        if not dry_run:
            shutil.move(str(src), out)
    if not dry_run:
        try:
            item.folder.rmdir()
        except OSError:
            pass
    return log


def write_prop_tscn(tscn_path: Path, png_path: Path, item: Item) -> None:
    with Image.open(png_path) as im:
        w, h = im.size

    name = tscn_path.stem
    coll = collision_for(w, h, item.collision)
    has_collision = "true" if (item.has_collision and coll is not None) else "false"
    interact_size = (float(w), min(float(h), 16.0))
    interact_pos = (0.0, -interact_size[1] / 2.0)

    tex_uid = godot_uid("tex:" + name)
    scene_uid = godot_uid("scene:" + name)
    template_uid = "uid://muzha_prop_template"

    rel_png = "res://" + str(png_path.relative_to(ROOT / "game")).replace("\\", "/")
    rel_template = "res://src/maps/props/PropTemplate.tscn"

    parts: list[str] = []
    load_steps = 4 if coll is None else 5
    parts.append(f'[gd_scene load_steps={load_steps} format=3 uid="{scene_uid}"]\n')
    parts.append(f'[ext_resource type="PackedScene" uid="{template_uid}" path="{rel_template}" id="4_tmpl"]')
    parts.append(f'[ext_resource type="Texture2D" path="{rel_png}" id="3_tex"]\n')

    if coll is not None:
        size, pos = coll
        parts.append(f'[sub_resource type="RectangleShape2D" id="1_rect"]\nsize = Vector2({size[0]}, {size[1]})\n')
    parts.append(f'[sub_resource type="RectangleShape2D" id="2_irect"]\nsize = Vector2({interact_size[0]}, {interact_size[1]})\n')

    parts.append(f'[node name="{name}" instance=ExtResource("4_tmpl")]\nhas_collision = {has_collision}\n')
    parts.append('[node name="Sprite2D" parent="." index="0"]\ntexture = ExtResource("3_tex")\n')
    if coll is not None:
        size, pos = coll
        parts.append(f'[node name="CollisionShape2D" parent="StaticBody2D" index="0"]\nposition = Vector2({pos[0]}, {pos[1]})\nshape = SubResource("1_rect")\n')
    parts.append(f'[node name="CollisionShape2D" parent="InteractArea" index="0"]\nposition = Vector2({interact_pos[0]}, {interact_pos[1]})\nshape = SubResource("2_irect")\n')

    tscn_path.write_text("\n".join(parts), encoding="utf-8")


def cmd_import(manifest_path: Path, dry_run: bool) -> int:
    items = load_manifest(manifest_path)
    warn_unlisted(manifest_path, items)
    for item in items:
        print(f"[{item.type}] {item.name} -> category={item.category} zone={item.zone} collision={item.collision}")
        if item.type == "prop":
            log = import_prop(item, dry_run)
        elif item.type == "autotile":
            log = import_autotile(item, dry_run)
        else:
            raise ValueError(f"{item.name}: unknown type {item.type!r}")
        for line in log[:4]:
            print(line)
        if len(log) > 4:
            print(f"  ... ({len(log) - 4} more)")
    print("\nDone." + ("  (dry-run, nothing changed)" if dry_run else ""))
    return 0


def cmd_init(temp_dir: Path) -> int:
    """Scaffold a manifest from existing temp/ folders so the artist only fills in intent."""
    out_path = temp_dir / "import.toml"
    if out_path.exists():
        print(f"refuse to overwrite {out_path}", file=sys.stderr)
        return 1
    folders = sorted(d for d in temp_dir.rglob("*") if d.is_dir() and any(d.glob("*.png")))
    lines = ["# Auto-scaffolded import manifest. Fill in category/collision per item.\n"]
    for d in folders:
        rel = d.relative_to(ROOT).as_posix()
        guessed_zone = d.parent.name if d.parent.parent.name == "tilesets" else ""
        lines.append("[[items]]")
        lines.append(f'folder = "{rel}"')
        lines.append('type = "prop"          # "prop" | "autotile"')
        lines.append('category = "urban"     # "urban" | "nature"')
        if guessed_zone:
            lines.append(f'zone = "{guessed_zone}"     # only used when type="autotile"')
        lines.append('has_collision = true')
        lines.append('collision = "full"     # none | bottom_16x8 | bottom_16x16 | full | "WxH"')
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_path.relative_to(ROOT)} with {len(folders)} entries — edit it before running import.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("manifest", nargs="?", type=Path, help="path to TOML manifest")
    p.add_argument("--init", type=Path, metavar="TEMP_DIR", help="scaffold a manifest from a temp/ folder")
    p.add_argument("--dry-run", action="store_true", help="show what would happen without moving files")
    args = p.parse_args()

    if args.init:
        return cmd_init(args.init.resolve())
    if not args.manifest:
        p.error("manifest path required (or use --init)")
    return cmd_import(args.manifest.resolve(), args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
