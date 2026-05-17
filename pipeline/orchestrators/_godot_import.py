"""Helpers for copying art-pipeline output into the Godot project tree.

Used by the `import_to_godot` stage of every orchestrator. Single source of
truth for the path layout under `game/assets/textures/` and `game/src/maps/`.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from PIL import Image

UID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"

COLLISION_PRESETS: dict[str, tuple[float, float] | str | None] = {
    "none": None,
    "bottom_16x8": (16.0, 8.0),
    "bottom_16x16": (16.0, 16.0),
    "full": "full",
}


def project_root() -> Path:
    # _godot_import.py → orchestrators/ → pipeline/ → <repo root>
    return Path(__file__).resolve().parents[2]


def godot_uid(seed: str) -> str:
    h = hashlib.sha1(seed.encode()).digest()
    n = int.from_bytes(h[:8], "big")
    return "uid://c" + "".join(UID_ALPHABET[(n >> (i * 5)) % 36] for i in range(13))


def _parse_collision(spec: str) -> tuple[float, float] | str | None:
    if spec in COLLISION_PRESETS:
        return COLLISION_PRESETS[spec]
    if "x" in spec.lower():
        try:
            w, h = spec.lower().split("x")
            return (float(w), float(h))
        except ValueError:
            pass
    raise ValueError(f"unknown collision spec: {spec!r}")


def _collision_rect(png_w: int, png_h: int, spec: str) -> tuple[tuple[float, float], tuple[float, float]] | None:
    parsed = _parse_collision(spec)
    if parsed is None:
        return None
    if parsed == "full":
        return ((float(png_w), float(png_h)), (0.0, -png_h / 2.0))
    w, h = parsed
    return ((w, h), (0.0, -h / 2.0))


def import_prop(
    src_png: Path, name: str, collision: str, has_collision: bool,
    *, root: Path | None = None,
) -> tuple[Path, Path]:
    """Copy prop PNG into Godot tree and generate a .tscn from PropTemplate.

    Returns (game_png_path, game_tscn_path), both absolute.
    """
    root = root or project_root()
    png_dest = root / "game" / "assets" / "textures" / "props" / f"{name}.png"
    tscn_dest = root / "game" / "src" / "maps" / "props" / f"{name}.tscn"
    png_dest.parent.mkdir(parents=True, exist_ok=True)
    tscn_dest.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(src_png, png_dest)
    _write_prop_tscn(tscn_dest, png_dest, name, collision, has_collision, root=root)
    return png_dest, tscn_dest


def _write_prop_tscn(
    tscn_path: Path, png_path: Path, name: str, collision: str, has_collision: bool,
    *, root: Path,
) -> None:
    with Image.open(png_path) as im:
        w, h = im.size

    coll = _collision_rect(w, h, collision)
    has_coll = "true" if (has_collision and coll is not None) else "false"
    interact_size = (float(w), min(float(h), 16.0))
    interact_pos = (0.0, -interact_size[1] / 2.0)

    # 從現有 .png.import 讀真正 UID;沒有就先生個 deterministic 的(Godot 之後會覆寫)
    import_file = png_path.with_suffix(png_path.suffix + ".import")
    tex_uid: str | None = None
    if import_file.exists():
        import re as _re
        m = _re.search(r'uid="(uid://[^"]+)"', import_file.read_text(encoding="utf-8"))
        if m:
            tex_uid = m.group(1)
    if tex_uid is None:
        tex_uid = godot_uid("tex:" + name)
    scene_uid = godot_uid("scene:" + name)
    template_uid = "uid://muzha_prop_template"

    rel_png = "res://" + str(png_path.relative_to(root / "game")).replace("\\", "/")
    rel_template = "res://src/maps/props/PropTemplate.tscn"

    parts: list[str] = []
    load_steps = 4 if coll is None else 5
    parts.append(f'[gd_scene load_steps={load_steps} format=3 uid="{scene_uid}"]\n')
    parts.append(f'[ext_resource type="PackedScene" uid="{template_uid}" path="{rel_template}" id="4_tmpl"]')
    parts.append(f'[ext_resource type="Texture2D" uid="{tex_uid}" path="{rel_png}" id="3_tex"]\n')

    if coll is not None:
        size, _ = coll
        parts.append(f'[sub_resource type="RectangleShape2D" id="1_rect"]\nsize = Vector2({size[0]}, {size[1]})\n')
    parts.append(
        f'[sub_resource type="RectangleShape2D" id="2_irect"]\n'
        f'size = Vector2({interact_size[0]}, {interact_size[1]})\n'
    )

    parts.append(f'[node name="{name}" instance=ExtResource("4_tmpl")]\nhas_collision = {has_coll}\n')
    # Bake foot-anchor offset into the .tscn so editor view matches runtime.
    # Prop.gd's _ready() will re-apply the same value when foot_anchor is on;
    # we just need this here so the editor sees the correct layout without
    # requiring the script to be @tool-mode.
    parts.append(
        f'[node name="Sprite2D" parent="." index="0"]\n'
        f'texture = ExtResource("3_tex")\n'
        f'offset = Vector2(0, {-h / 2.0})\n'
    )
    if coll is not None:
        size, pos = coll
        parts.append(
            f'[node name="CollisionShape2D" parent="StaticBody2D" index="0"]\n'
            f'position = Vector2({pos[0]}, {pos[1]})\n'
            f'shape = SubResource("1_rect")\n'
        )
    parts.append(
        f'[node name="CollisionShape2D" parent="InteractArea" index="0"]\n'
        f'position = Vector2({interact_pos[0]}, {interact_pos[1]})\n'
        f'shape = SubResource("2_irect")\n'
    )
    tscn_path.write_text("\n".join(parts), encoding="utf-8")


def import_tileset(src_png: Path, name: str, *, root: Path | None = None) -> Path:
    root = root or project_root()
    dest = root / "game" / "assets" / "textures" / "tilesets" / f"{name}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_png, dest)
    return dest


def import_character_spritesheet(
    src_png: Path, src_atlas_json: Path, name: str,
    *, root: Path | None = None,
) -> tuple[Path, Path]:
    root = root or project_root()
    png_dest = root / "game" / "assets" / "textures" / "characters" / f"{name}.png"
    json_dest = root / "game" / "assets" / "textures" / "characters" / f"{name}.json"
    png_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_png, png_dest)
    shutil.copyfile(src_atlas_json, json_dest)
    return png_dest, json_dest
