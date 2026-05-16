"""Build a Godot zone .tscn from YAML layout(s).

Input modes:
  - **Single-era zone**:`story/chapters/<chapter>/zones/<slug>.yaml`,YAML 沒 `era` 欄位
  - **Hybrid era zone**:`story/chapters/<chapter>/zones/<slug>/<era>.yaml` × N,
    每份 YAML 同 `zone:` slug + 不同 `era:` 值

CLI:
    python build_zone.py <name>            # 可以是 folder name 或 flat yaml stem
    python build_zone.py <name> --force    # 覆蓋已存在 .tscn

Hybrid era 機制:
  - 每份 YAML 的 props / npcs 都 emit 進 flat YSortRoot,並標 `groups=["era_<era>"]`
  - Y-sort 不被破壞(prop 直接是 YSortRoot 的 child,而不是 Era wrapper 的 child)
  - EraManager runtime 用 `get_tree().get_nodes_in_group("era_<x>")` toggle `.visible`
  - 初始可見的 era 由 `EraTint` CanvasModulate 節點 + 初始 visible 旗標決定:
    chapter 1 預設 modern 可見,1983 隱藏
  - Terrain / tilemap / player_spawn 由 "first" era YAML 提供(目前按字母序),
    其他 era YAML 的同欄位若不一致會 warn

Terrain cells 直接 bake 進 root 節點的 `terrain_cells` Array[Vector2i] —
Godot 端用 `tools/zone_baker.gd` `@tool` 按鈕一鍵塗。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
GAME_ROOT = REPO_ROOT / "game"
ZONES_OUT = GAME_ROOT / "src" / "maps" / "zones"
PROPS_DIR = GAME_ROOT / "src" / "maps" / "props"
NPC_DEFS_DIR = GAME_ROOT / "src" / "entities" / "npcs" / "definitions"
CHAPTER_NPCS_GLOB = GAME_ROOT / "src" / "chapters"   # */npcs/<id>.tres
CHARACTERS_TEX_DIR = GAME_ROOT / "assets" / "textures" / "characters"

ISO_TILE_W = 32
ISO_TILE_H = 16

# Chapter 1 預設 era;未來可從 YAML 或 chapter.tres 讀
DEFAULT_INITIAL_ERA = "modern"

# 16-tile Wang peering-bit config — mirrors zone_iso_test.tscn pattern.
ATLAS_PEERING_BITS: list[tuple[str, int | None, tuple[int, int, int, int]]] = [
    ("0:3", 0,    (0, 0, 0, 0)),
    ("3:3", None, (0, 0, 0, 1)),
    ("0:2", None, (1, 0, 0, 0)),
    ("1:2", None, (1, 0, 0, 1)),
    ("0:0", None, (0, 0, 1, 0)),
    ("3:2", None, (0, 0, 1, 1)),
    ("2:3", None, (1, 0, 1, 0)),
    ("3:1", None, (1, 0, 1, 1)),
    ("1:3", None, (0, 1, 0, 0)),
    ("0:1", None, (0, 1, 0, 1)),
    ("1:0", None, (1, 1, 0, 0)),
    ("2:2", None, (1, 1, 0, 1)),
    ("3:0", None, (0, 1, 1, 0)),
    ("2:0", None, (0, 1, 1, 1)),
    ("1:1", None, (1, 1, 1, 0)),
    ("2:1", 1,    (1, 1, 1, 1)),
]

TILESETS_DIR = GAME_ROOT / "assets" / "textures" / "tilesets"


def iso_cell_to_pixel(cx: int, cy: int) -> tuple[int, int]:
    x = (cx - cy) * (ISO_TILE_W // 2)
    y = (cx + cy) * (ISO_TILE_H // 2)
    return x, y


ANCHOR_RE = re.compile(r"^relative_to\(([a-zA-Z0-9_]+)\)$")


def resolve_anchor(
    anchor: str | None,
    cell: list[int] | None,
    size: tuple[int, int],
    placed: dict[str, tuple[int, int]],
) -> tuple[int, int]:
    if cell is not None:
        return int(cell[0]), int(cell[1])
    if anchor is None:
        return 0, 0
    w, h = size
    half_w, half_h = w // 2, h // 2
    if anchor == "center":
        return 0, 0
    if anchor in ("north_wall", "north"):
        return 0, -half_h
    if anchor in ("south_wall", "south", "entrance"):
        return 0, half_h - 1
    if anchor in ("east_wall", "east"):
        return half_w - 1, 0
    if anchor in ("west_wall", "west"):
        return -half_w, 0
    m = ANCHOR_RE.match(anchor)
    if m:
        ref = m.group(1)
        if ref not in placed:
            raise ValueError(
                f"relative_to({ref}): {ref!r} not yet placed. Order props/npcs so "
                f"references appear earlier in the YAML."
            )
        return placed[ref]
    raise ValueError(f"Unknown anchor: {anchor!r}")


def load_uid(tscn_path: Path) -> str | None:
    if not tscn_path.exists():
        return None
    try:
        text = tscn_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = re.search(r'uid="(uid://[^"]+)"', text)
    return m.group(1) if m else None


def resolve_prop(prop_id: str) -> dict[str, Any]:
    tscn = PROPS_DIR / f"{prop_id}.tscn"
    if not tscn.exists():
        raise FileNotFoundError(f"prop .tscn missing: {tscn}")
    return {
        "kind": "prop",
        "id": prop_id,
        "path": f"res://src/maps/props/{prop_id}.tscn",
        "uid": load_uid(tscn),
    }


def _find_npc_tres(npc_id: str) -> Path | None:
    """先找 entities/npcs/definitions/ 共用基底,再找 chapters/*/npcs/ 章節限定。"""
    base = NPC_DEFS_DIR / f"{npc_id}.tres"
    if base.exists():
        return base
    matches = list(CHAPTER_NPCS_GLOB.glob(f"*/npcs/{npc_id}.tres"))
    return matches[0] if matches else None


def resolve_npc(npc_id: str) -> dict[str, Any]:
    tres = _find_npc_tres(npc_id)
    if tres is not None:
        rel = "res://" + str(tres.relative_to(GAME_ROOT)).replace("\\", "/")
        return {
            "kind": "npc_config",
            "id": npc_id,
            "config_path": rel,
            "config_uid": load_uid(tres),
        }
    png = CHARACTERS_TEX_DIR / f"{npc_id}.png"
    if png.exists():
        meta_json = CHARACTERS_TEX_DIR / f"{npc_id}.json"
        frame_w = frame_h = 64
        if meta_json.exists():
            try:
                meta = json.loads(meta_json.read_text(encoding="utf-8"))
                fs = meta.get("frame_size") or [64, 64]
                frame_w, frame_h = int(fs[0]), int(fs[1])
            except (OSError, ValueError, KeyError):
                pass
        return {
            "kind": "npc_sprite",
            "id": npc_id,
            "tex_path": f"res://assets/textures/characters/{npc_id}.png",
            "tex_uid": load_uid(png.with_suffix(".png.import")),
            "frame_w": frame_w,
            "frame_h": frame_h,
        }
    raise FileNotFoundError(
        f"npc {npc_id!r}: neither {tres.relative_to(REPO_ROOT)} nor "
        f"{png.relative_to(REPO_ROOT)} found."
    )


def compute_terrain_cells(tilemap: dict[str, Any], size: tuple[int, int]) -> list[tuple[int, int]]:
    fill = tilemap.get("fill", "rect")
    if fill != "rect":
        raise ValueError(f"tilemap.fill={fill!r} not supported yet (only 'rect').")
    w, h = size
    half_w, half_h = w // 2, h // 2
    cells: list[tuple[int, int]] = []
    for cx in range(-half_w, w - half_w):
        for cy in range(-half_h, h - half_h):
            cells.append((cx, cy))
    return cells


# === Resolution(把 YAML 轉成 placed prop/npc list) ===========================

def resolve_layout(
    layout: dict[str, Any], size: tuple[int, int]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], tuple[int, int]]:
    """Resolve one YAML 的 props/npcs/player_spawn → placed lists + spawn pixel.

    Hybrid era zones:node name 自動加 `_<era>` suffix 避免兩 era 同 prop 撞名
    (e.g. shop_counter_wood 同時出現在 1983 + modern → `shop_counter_wood_1983`
    與 `shop_counter_wood_modern`)。
    """
    placed: dict[str, tuple[int, int]] = {}
    era = layout.get("era")
    suffix = f"_{era}" if era is not None else ""

    resolved_props: list[dict[str, Any]] = []
    for entry in layout.get("props", []):
        info = resolve_prop(entry["id"])
        base_name = entry.get("rename", entry["id"])
        node_name = base_name + suffix
        cx, cy = resolve_anchor(entry.get("anchor"), entry.get("cell"), size, placed)
        ox, oy = entry.get("offset", [0, 0])
        cx, cy = cx + ox, cy + oy
        px, py = iso_cell_to_pixel(cx, cy)
        # placed dict 用 base_name(不含 era 後綴)讓 relative_to() 跨同 era 內好找
        placed[base_name] = (cx, cy)
        resolved_props.append({**info, "node_name": node_name, "px": px, "py": py, "era": era})

    resolved_transitions: list[dict[str, Any]] = []
    for entry in layout.get("transitions", []):
        cx, cy = resolve_anchor(entry.get("anchor"), entry.get("cell"), size, placed)
        ox, oy = entry.get("offset", [0, 0])
        cx, cy = cx + ox, cy + oy
        px, py = iso_cell_to_pixel(cx, cy)
        base_name: str = entry.get(
            "rename", _pascal("to_" + entry["target_zone"].replace("zone_", ""))
        )
        node_name: str = base_name + suffix   # 同 prop/npc 邏輯,避免兩 era 撞名
        resolved_transitions.append({
            "target_zone": entry["target_zone"],
            "entry_point": entry.get("entry_point", "default"),
            "label": entry.get("label", ""),
            "node_name": node_name,
            "px": px, "py": py,
            "era": era,
        })

    resolved_npcs: list[dict[str, Any]] = []
    for entry in layout.get("npcs", []):
        info = resolve_npc(entry["id"])
        base_name = entry.get("rename", _pascal(entry["id"]))
        node_name = base_name + suffix
        cx, cy = resolve_anchor(entry.get("anchor"), entry.get("cell"), size, placed)
        ox, oy = entry.get("offset", [0, 0])
        cx, cy = cx + ox, cy + oy
        px, py = iso_cell_to_pixel(cx, cy)
        placed[base_name] = (cx, cy)
        resolved_npcs.append({**info, "node_name": node_name, "px": px, "py": py, "era": era})

    spawn = layout.get("player_spawn") or {"anchor": "south_wall", "offset": [0, -1]}
    scx, scy = resolve_anchor(spawn.get("anchor"), spawn.get("cell"), size, placed)
    sox, soy = spawn.get("offset", [0, 0])
    spawn_px = iso_cell_to_pixel(scx + sox, scy + soy)

    return resolved_props, resolved_npcs, resolved_transitions, spawn_px


# === .tscn emission =========================================================

EXT_BAKER_PATH = "res://tools/zone_baker.gd"


def emit_tscn(layouts: list[dict[str, Any]], out_path: Path) -> None:
    """Emit a single .tscn from one-or-more YAML layouts (multi-era merge)."""
    # 排序:single-era 走第一份;multi-era 按字母 era 排序(1983 在 modern 前)
    layouts = sorted(layouts, key=lambda l: l.get("era") or "")
    primary = layouts[0]
    zone_name = primary["zone"]
    size = tuple(primary.get("size", [20, 15]))
    label = primary.get("label", zone_name)
    tilemap_cfg = primary.get("tilemap", {})
    terrain_id = int(tilemap_cfg.get("terrain", 1))
    is_hybrid = len(layouts) > 1 or primary.get("era") is not None

    # Warn on inconsistent shared fields
    for l in layouts[1:]:
        if tuple(l.get("size", size)) != size:
            print(
                f"warning: era={l.get('era')!r} size mismatch ({l.get('size')} vs {size}). "
                f"Using primary's size.",
                file=sys.stderr,
            )

    # Resolve every era's props/npcs/transitions
    all_props: list[dict[str, Any]] = []
    all_npcs: list[dict[str, Any]] = []
    all_transitions: list[dict[str, Any]] = []
    spawn_px: tuple[int, int] | None = None
    for l in layouts:
        props, npcs, transitions, sp = resolve_layout(l, size)
        all_props.extend(props)
        all_npcs.extend(npcs)
        all_transitions.extend(transitions)
        # Take spawn from primary (alphabetically first era)
        if spawn_px is None:
            spawn_px = sp
    assert spawn_px is not None
    spx, spy = spawn_px

    terrain_cells = compute_terrain_cells(tilemap_cfg, size)
    atlas_name = tilemap_cfg.get("atlas")

    # --- Build ext_resource section ---------------------------------------
    ext_lines: list[str] = []
    sub_lines: list[str] = []
    ext_id_counter = 1
    ext_ids: dict[str, str] = {}

    def add_ext(key: str, line_tmpl: str) -> str:
        nonlocal ext_id_counter
        if key in ext_ids:
            return ext_ids[key]
        rid = f"{ext_id_counter}_{re.sub(r'[^a-z0-9]+', '_', key.lower())[:20]}"
        ext_id_counter += 1
        ext_ids[key] = rid
        ext_lines.append(line_tmpl.format(id=rid))
        return rid

    baker_id = add_ext(
        "baker",
        f'[ext_resource type="Script" path="{EXT_BAKER_PATH}" id="{{id}}"]',
    )
    tmd_script_id = add_ext(
        "tmd_script",
        '[ext_resource type="Script" uid="uid://cjk8nronimk5r" '
        'path="res://addons/TileMapDual/tile_map_dual.gd" id="{id}"]',
    )
    ghost_mat_id = add_ext(
        "ghost_mat",
        '[ext_resource type="Material" uid="uid://cmbcfxlkxxnwq" '
        'path="res://addons/TileMapDual/ghost_material.tres" id="{id}"]',
    )
    player_id = add_ext(
        "player",
        '[ext_resource type="PackedScene" path="res://src/entities/player/Player.tscn" id="{id}"]',
    )
    pcam_script_id = add_ext(
        "pcam_script",
        '[ext_resource type="Script" '
        'path="res://addons/phantom_camera/scripts/phantom_camera/phantom_camera_2d.gd" '
        'id="{id}"]',
    )
    pcam_host_script_id = add_ext(
        "pcam_host_script",
        '[ext_resource type="Script" '
        'path="res://addons/phantom_camera/scripts/phantom_camera_host/phantom_camera_host.gd" '
        'id="{id}"]',
    )

    tileset_subres_id: str | None = None
    if atlas_name:
        atlas_png = TILESETS_DIR / f"{atlas_name}.png"
        if not atlas_png.exists():
            raise FileNotFoundError(
                f"tilemap.atlas={atlas_name!r}: missing {atlas_png.relative_to(REPO_ROOT)}"
            )
        atlas_uid = load_uid(TILESETS_DIR / f"{atlas_name}.png.import")
        uid_attr = f' uid="{atlas_uid}"' if atlas_uid else ""
        atlas_ext_id = add_ext(
            f"atlas_{atlas_name}",
            f'[ext_resource type="Texture2D"{uid_attr} '
            f'path="res://assets/textures/tilesets/{atlas_name}.png" id="{{id}}"]',
        )
        atlas_src_sub_id = f"TileSetAtlasSource_{atlas_name}"
        tileset_subres_id = f"TileSet_{atlas_name}"

        atlas_block: list[str] = [
            f'[sub_resource type="TileSetAtlasSource" id="{atlas_src_sub_id}"]',
            f'texture = ExtResource("{atlas_ext_id}")',
            f'texture_region_size = Vector2i({ISO_TILE_W}, {ISO_TILE_H})',
        ]
        for cell, terrain_val, (r, b, l_, t) in ATLAS_PEERING_BITS:
            atlas_block.append(f"{cell}/0 = 0")
            atlas_block.append(f"{cell}/0/terrain_set = 0")
            if terrain_val is not None:
                atlas_block.append(f"{cell}/0/terrain = {terrain_val}")
            atlas_block.append(f"{cell}/0/terrains_peering_bit/right_corner = {r}")
            atlas_block.append(f"{cell}/0/terrains_peering_bit/bottom_corner = {b}")
            atlas_block.append(f"{cell}/0/terrains_peering_bit/left_corner = {l_}")
            atlas_block.append(f"{cell}/0/terrains_peering_bit/top_corner = {t}")
        sub_lines.append("\n".join(atlas_block))

        tileset_block = [
            f'[sub_resource type="TileSet" id="{tileset_subres_id}"]',
            'tile_shape = 1',
            f'tile_size = Vector2i({ISO_TILE_W}, {ISO_TILE_H})',
            'terrain_set_0/mode = 1',
            'terrain_set_0/terrain_0/name = "<any>"',
            'terrain_set_0/terrain_0/color = Color(0.93333334, 0.50980395, 0.93333334, 1)',
            f'terrain_set_0/terrain_1/name = "FG -{atlas_name}.png"',
            'terrain_set_0/terrain_1/color = Color(0.5, 0.4375, 0.25, 1)',
            f'sources/0 = SubResource("{atlas_src_sub_id}")',
        ]
        sub_lines.append("\n".join(tileset_block))

    base_npc_id: str | None = None
    if any(p["kind"] == "npc_config" for p in all_npcs):
        base_npc_id = add_ext(
            "base_npc",
            '[ext_resource type="PackedScene" path="res://src/entities/npcs/BaseNPC.tscn" id="{id}"]',
        )

    zta_id: str | None = None
    if all_transitions:
        zta_id = add_ext(
            "zone_transition_area",
            '[ext_resource type="PackedScene" '
            'path="res://src/core/components/ZoneTransitionArea.tscn" id="{id}"]',
        )

    for p in all_props:
        uid_attr = f' uid="{p["uid"]}"' if p["uid"] else ""
        p["ext_id"] = add_ext(
            f"prop_{p['id']}",
            f'[ext_resource type="PackedScene"{uid_attr} path="{p["path"]}" id="{{id}}"]',
        )

    for n in all_npcs:
        if n["kind"] == "npc_config":
            uid_attr = f' uid="{n["config_uid"]}"' if n["config_uid"] else ""
            n["ext_id"] = add_ext(
                f"npccfg_{n['id']}",
                f'[ext_resource type="Resource"{uid_attr} path="{n["config_path"]}" id="{{id}}"]',
            )
        else:
            n["ext_id"] = add_ext(
                f"npctex_{n['id']}",
                f'[ext_resource type="Texture2D" path="{n["tex_path"]}" id="{{id}}"]',
            )

    # --- Build node section -----------------------------------------------
    cells_literal = ", ".join(f"Vector2i({c[0]}, {c[1]})" for c in terrain_cells)

    nodes: list[str] = []
    yaml_paths_literal = ", ".join(f'"{p}"' for p in primary.get("_yaml_paths", []))
    nodes.append(
        f'[node name="{_pascal(zone_name)}" type="Node2D"]\n'
        f'script = ExtResource("{baker_id}")\n'
        f"terrain_cells = Array[Vector2i]([{cells_literal}])\n"
        f"terrain_id = {terrain_id}\n"
        f"yaml_paths = Array[String]([{yaml_paths_literal}])"
    )
    nodes.append('[node name="ZoneLabel" type="Label" parent="."]\n'
                 'modulate = Color(1, 1, 1, 0.5)\n'
                 'offset_left = -120.0\n'
                 'offset_top = -180.0\n'
                 'offset_right = 120.0\n'
                 'offset_bottom = -160.0\n'
                 'theme_override_font_sizes/font_size = 14\n'
                 'horizontal_alignment = 1\n'
                 f'text = "{label}"')

    # EraTint (CanvasModulate) — EraManager 之後 tween color 做時空 mood
    if is_hybrid:
        nodes.append('[node name="EraTint" type="CanvasModulate" parent="."]\n'
                     '# EraManager 控制此節點的 color。預設 identity(白色不偏色)。\n'
                     'color = Color(1, 1, 1, 1)')

    nodes.append('[node name="TileMapLayer" type="TileMapLayer" parent="."]')
    tile_set_line = (
        f'tile_set = SubResource("{tileset_subres_id}")\n' if tileset_subres_id else ""
    )
    nodes.append(
        '[node name="TileMapDual" type="TileMapLayer" parent="TileMapLayer"]\n'
        f'material = ExtResource("{ghost_mat_id}")\n'
        f'{tile_set_line}'
        f'script = ExtResource("{tmd_script_id}")\n'
        'godot_4_3_compatibility = false\n'
        'metadata/_custom_type_script = "uid://cjk8nronimk5r"'
    )

    nodes.append('[node name="YSortRoot" type="Node2D" parent="."]\n'
                 'y_sort_enabled = true')

    # Player(永遠存在,不分 era)
    nodes.append(
        f'[node name="Player" parent="YSortRoot" instance=ExtResource("{player_id}")]\n'
        f"position = Vector2({spx}, {spy})"
    )
    # Camera2D(實體鏡頭,scene-root level) — 被 PhantomCameraHost 接管。
    # `current = true` 確保它是 viewport 的 active camera。
    # `position_smoothing_enabled = false` 跟 PhantomCamera 的 tween 不重疊。
    nodes.append('[node name="Camera2D" type="Camera2D" parent="."]\n'
                 'current = true\n'
                 'position_smoothing_enabled = false\n'
                 'zoom = Vector2(3, 3)')
    nodes.append(
        '[node name="PhantomCameraHost" type="Node" parent="Camera2D"]\n'
        f'script = ExtResource("{pcam_host_script_id}")'
    )
    # 預設 PhantomCamera2D。tween_on_load=false 讓鏡頭一開始就 snap 到 Player。
    # 注意:`node_paths=PackedStringArray("follow_target")` 是必須的 ——
    # Godot 4 typed Node export 沒這個的話,NodePath 不會被解析成 Node 引用,
    # 結果 follow_target 在 runtime 是 null,GLUED 模式抓不到目標 → 鏡頭不動。
    nodes.append(
        '[node name="DefaultCam" type="Node2D" parent="." '
        'node_paths=PackedStringArray("follow_target")]\n'
        f'script = ExtResource("{pcam_script_id}")\n'
        'priority = 0\n'
        'follow_mode = 1\n'   # GLUED
        'follow_target = NodePath("../YSortRoot/Player")\n'
        'zoom = Vector2(3, 3)\n'
        'tween_on_load = false'
    )

    # Props
    for p in all_props:
        groups_attr = _era_groups_attr(p["era"])
        visible_line = _initial_visible_line(p["era"], is_hybrid)
        nodes.append(
            f'[node name="{p["node_name"]}" parent="YSortRoot" '
            f'instance=ExtResource("{p["ext_id"]}"){groups_attr}]\n'
            f"position = Vector2({p['px']}, {p['py']})"
            f"{visible_line}"
        )

    # Transitions(掛在獨立 Transitions Node2D 下,避免跟 YSortRoot 內 prop 混在一起)
    if all_transitions:
        nodes.append('[node name="Transitions" type="Node2D" parent="."]')
        for t in all_transitions:
            groups_attr = _era_groups_attr(t["era"])
            visible_line = _initial_visible_line(t["era"], is_hybrid)
            label_lines = ""
            if t["label"]:
                # 用 escape-friendly 寫法:label 寫進 Label 子節點
                pass  # 預設 ZoneTransitionArea.tscn 已內建 Label,改不便,先省略
            nodes.append(
                f'[node name="{t["node_name"]}" parent="Transitions" '
                f'instance=ExtResource("{zta_id}"){groups_attr}]\n'
                f"position = Vector2({t['px']}, {t['py']})\n"
                f'target_zone = "{t["target_zone"]}"\n'
                f'entry_point = "{t["entry_point"]}"'
                f"{visible_line}"
            )

    # NPCs
    for n in all_npcs:
        groups_attr = _era_groups_attr(n["era"])
        visible_line = _initial_visible_line(n["era"], is_hybrid)
        if n["kind"] == "npc_config":
            nodes.append(
                f'[node name="{n["node_name"]}" parent="YSortRoot" '
                f'instance=ExtResource("{base_npc_id}"){groups_attr}]\n'
                f"position = Vector2({n['px']}, {n['py']})\n"
                f'npc_config = ExtResource("{n["ext_id"]}")'
                f"{visible_line}"
            )
        else:
            fw, fh = n["frame_w"], n["frame_h"]
            nodes.append(
                f'[node name="{n["node_name"]}" type="Sprite2D" parent="YSortRoot"{groups_attr}]\n'
                f"position = Vector2({n['px']}, {n['py']})\n"
                f'texture = ExtResource("{n["ext_id"]}")\n'
                f"region_enabled = true\n"
                f"region_rect = Rect2(0, 0, {fw}, {fh})"
                f"{visible_line}"
            )

    header = '[gd_scene format=3]\n\n'
    sections = [header + "\n".join(ext_lines)]
    if sub_lines:
        sections.append("\n\n".join(sub_lines))
    sections.append("\n\n".join(nodes))
    body = "\n\n".join(sections) + "\n"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")


def _era_groups_attr(era: str | None) -> str:
    if era is None:
        return ""
    return f' groups=["era_{era}"]'


def _initial_visible_line(era: str | None, is_hybrid: bool) -> str:
    """Hybrid 場景:非 DEFAULT_INITIAL_ERA 的 era 預設隱藏(visible=false)。"""
    if not is_hybrid or era is None or era == DEFAULT_INITIAL_ERA:
        return ""
    return "\nvisible = false"


def _pascal(s: str) -> str:
    return "".join(part.capitalize() for part in s.split("_"))


# === YAML discovery =========================================================

def find_layouts(name: str) -> list[Path]:
    """Find YAML(s) for `name`。

    - Folder form:`story/chapters/*/zones/<name>/*.yaml` → multi era
    - Flat form:`story/chapters/*/zones/<name>.yaml` → single era
    """
    zones_glob = REPO_ROOT / "story" / "chapters"
    # Try folder form
    folders = list(zones_glob.glob(f"*/zones/{name}"))
    folders = [f for f in folders if f.is_dir()]
    if folders:
        yamls = sorted(folders[0].glob("*.yaml"))
        if not yamls:
            raise FileNotFoundError(f"folder {folders[0]} has no .yaml")
        return yamls
    # Flat form
    files = list(zones_glob.glob(f"*/zones/{name}.yaml"))
    if files:
        return [files[0]]
    raise FileNotFoundError(
        f"No YAML found for {name!r}. Tried:\n"
        f"  - story/chapters/*/zones/{name}/*.yaml (folder)\n"
        f"  - story/chapters/*/zones/{name}.yaml (flat)"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("name", help="Zone folder name OR flat YAML stem")
    ap.add_argument("--out", help="Override output .tscn path")
    ap.add_argument("--force", action="store_true", help="Overwrite existing .tscn")
    args = ap.parse_args()

    yaml_paths = find_layouts(args.name)
    layouts = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in yaml_paths]
    # Stash YAML repo-relative paths into first layout so emit_tscn can write them
    # onto the zone root(zone_baker.gd 的 Lock/Unlock 按鈕用)
    layouts[0]["_yaml_paths"] = [
        str(p.relative_to(REPO_ROOT)).replace("\\", "/") for p in yaml_paths
    ]

    # Validate: all layouts must share same `zone:` slug
    zones = {l["zone"] for l in layouts}
    if len(zones) > 1:
        print(
            f"refuse: YAMLs in folder have conflicting zone: {zones}",
            file=sys.stderr,
        )
        return 2
    zone_name = zones.pop()

    # frozen check
    for l, p in zip(layouts, yaml_paths):
        if l.get("frozen") is True:
            print(
                f"refuse: {p.relative_to(REPO_ROOT)} has `frozen: true`.",
                file=sys.stderr,
            )
            return 2

    out = Path(args.out) if args.out else ZONES_OUT / f"{zone_name}.tscn"
    if out.exists() and not args.force:
        print(
            f"refuse: {out.relative_to(REPO_ROOT)} already exists. Pass --force.",
            file=sys.stderr,
        )
        return 2

    emit_tscn(layouts, out)

    summary = {
        "zone": zone_name,
        "yaml_count": len(yaml_paths),
        "eras": sorted([l.get("era") for l in layouts if l.get("era")]),
        "size": layouts[0].get("size"),
        "props": sum(len(l.get("props", [])) for l in layouts),
        "npcs": sum(len(l.get("npcs", [])) for l in layouts),
        "out": str(out.relative_to(REPO_ROOT)),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
