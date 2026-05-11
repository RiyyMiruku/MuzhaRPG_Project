# Art Pipeline Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 art-pipeline 與 Godot 匯入統合成單一流程,扁平化資產結構,廢除 `scripts/import_assets.py`。

**Architecture:** 4 個 orchestrator (`prop.py`/`autotile.py`/`npc_static.py`/`npc_moving.py`) 都加 `import_to_godot` 終端 stage,共用模組 `_godot_import.py` 處理 PNG 複製與 .tscn 生成。資料夾扁平化 (`game/assets/textures/{props,tilesets,characters,portraits}/<name>.png`),廢除 `environment/` 中間層與 `urban/nature` 分類。`manifest.json` 擴展為生成+匯入狀態的單一索引。除 `iso_test` 外既有素材全部刪除,後續用新 pipeline 重生。

**Tech Stack:** Python 3.13 (uv), Pillow, Godot 4.6, GDScript, JSON manifest, pytest.

---

## File Structure (after refactor)

```
art_source/
├── pipeline/
│   ├── output/
│   │   ├── manifest.json                           ← 生成 + import 狀態
│   │   ├── characters/<name>/{rotations,animations,spritesheet}/
│   │   ├── tilesets/<name>/<name>_iso.png
│   │   └── objects/<name>/<name>.png
│   ├── orchestrators/
│   │   ├── _common.py                              ← 既有
│   │   ├── _godot_import.py                        ← 新增 (Task 1)
│   │   ├── prop.py / autotile.py / npc_*.py        ← 修改
│   │   └── ...
│   └── manifest.py                                 ← schema 擴展 (Task 2)
└── portraits/                                      ← 保留 (對話頭像原料)

game/
├── assets/
│   └── textures/
│       ├── props/<name>.png                        ← 扁平
│       ├── tilesets/<name>.png                     ← 扁平
│       ├── characters/<name>.png + <name>.json     ← 扁平,per-character JSON
│       ├── portraits/<name>.png                    ← 保留
│       └── iso_test/                               ← 保留 (試驗場素材)
└── src/
    └── maps/
        └── props/
            ├── PropTemplate.tscn / Prop.gd          ← 保留
            └── <name>.tscn                         ← 扁平

scripts/
├── generate_spritesheet.py                          ← 重寫 (Task 3)
└── test_ping.py                                    ← 保留

刪除:
- scripts/import_assets.py
- scripts/import-assets-guide.md
- game/assets/textures/environment/         (所有 props + tilesets,iso_test 不在此)
- game/src/maps/props/{urban,nature}/
- game/assets/spritesheet_cache/
- art_source/characters/                    (舊位置)
- temp/
```

---

## Task 1: 共用 Godot import 模組

**Files:**
- Create: `art_source/pipeline/orchestrators/_godot_import.py`
- Test: `art_source/pipeline/tests/test_godot_import.py`

- [ ] **Step 1: Write failing test for `godot_uid`**

```python
# art_source/pipeline/tests/test_godot_import.py
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrators._godot_import import godot_uid


def test_godot_uid_deterministic():
    assert godot_uid("tex:lantern_red") == godot_uid("tex:lantern_red")

def test_godot_uid_format():
    uid = godot_uid("tex:lantern_red")
    assert uid.startswith("uid://c")
    assert len(uid) == len("uid://c") + 13

def test_godot_uid_distinct():
    assert godot_uid("a") != godot_uid("b")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest art_source/pipeline/tests/test_godot_import.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement module**

```python
# art_source/pipeline/orchestrators/_godot_import.py
"""Helpers for copying art-pipeline output into the Godot project tree.

Used by the `import_to_godot` stage of every orchestrator. Single source of
truth for the path layout under `game/assets/textures/` and `game/src/maps/`.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Literal

from PIL import Image

UID_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"

CollisionSpec = Literal["none", "bottom_16x8", "bottom_16x16", "full"] | str

COLLISION_PRESETS: dict[str, tuple[float, float] | str | None] = {
    "none": None,
    "bottom_16x8": (16.0, 8.0),
    "bottom_16x16": (16.0, 16.0),
    "full": "full",
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


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
    src_png: Path, name: str, collision: str, has_collision: bool
) -> tuple[Path, Path]:
    """Copy prop PNG into Godot tree and generate a .tscn from PropTemplate.

    Returns (game_png_path, game_tscn_path), both absolute.
    """
    root = project_root()
    png_dest = root / "game" / "assets" / "textures" / "props" / f"{name}.png"
    tscn_dest = root / "game" / "src" / "maps" / "props" / f"{name}.tscn"
    png_dest.parent.mkdir(parents=True, exist_ok=True)
    tscn_dest.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(src_png, png_dest)
    _write_prop_tscn(tscn_dest, png_dest, name, collision, has_collision)
    return png_dest, tscn_dest


def _write_prop_tscn(
    tscn_path: Path, png_path: Path, name: str, collision: str, has_collision: bool
) -> None:
    with Image.open(png_path) as im:
        w, h = im.size

    coll = _collision_rect(w, h, collision)
    has_coll = "true" if (has_collision and coll is not None) else "false"
    interact_size = (float(w), min(float(h), 16.0))
    interact_pos = (0.0, -interact_size[1] / 2.0)

    tex_uid = godot_uid("tex:" + name)
    scene_uid = godot_uid("scene:" + name)
    template_uid = "uid://muzha_prop_template"

    rel_png = "res://" + str(png_path.relative_to(project_root() / "game")).replace("\\", "/")
    rel_template = "res://src/maps/props/PropTemplate.tscn"

    parts: list[str] = []
    load_steps = 4 if coll is None else 5
    parts.append(f'[gd_scene load_steps={load_steps} format=3 uid="{scene_uid}"]\n')
    parts.append(f'[ext_resource type="PackedScene" uid="{template_uid}" path="{rel_template}" id="4_tmpl"]')
    parts.append(f'[ext_resource type="Texture2D" path="{rel_png}" id="3_tex"]\n')

    if coll is not None:
        size, _ = coll
        parts.append(f'[sub_resource type="RectangleShape2D" id="1_rect"]\nsize = Vector2({size[0]}, {size[1]})\n')
    parts.append(
        f'[sub_resource type="RectangleShape2D" id="2_irect"]\n'
        f'size = Vector2({interact_size[0]}, {interact_size[1]})\n'
    )

    parts.append(f'[node name="{name}" instance=ExtResource("4_tmpl")]\nhas_collision = {has_coll}\n')
    parts.append('[node name="Sprite2D" parent="." index="0"]\ntexture = ExtResource("3_tex")\n')
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


def import_tileset(src_png: Path, name: str) -> Path:
    root = project_root()
    dest = root / "game" / "assets" / "textures" / "tilesets" / f"{name}.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_png, dest)
    return dest


def import_character_spritesheet(
    src_png: Path, src_atlas_json: Path, name: str
) -> tuple[Path, Path]:
    root = project_root()
    png_dest = root / "game" / "assets" / "textures" / "characters" / f"{name}.png"
    json_dest = root / "game" / "assets" / "textures" / "characters" / f"{name}.json"
    png_dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_png, png_dest)
    shutil.copyfile(src_atlas_json, json_dest)
    return png_dest, json_dest
```

- [ ] **Step 4: Add tests for collision parsing and prop import**

```python
# Append to art_source/pipeline/tests/test_godot_import.py
import pytest
from orchestrators._godot_import import _parse_collision, _collision_rect


def test_parse_collision_preset():
    assert _parse_collision("none") is None
    assert _parse_collision("bottom_16x16") == (16.0, 16.0)
    assert _parse_collision("full") == "full"

def test_parse_collision_custom():
    assert _parse_collision("24x12") == (24.0, 12.0)

def test_parse_collision_invalid():
    with pytest.raises(ValueError):
        _parse_collision("garbage")

def test_collision_rect_full():
    assert _collision_rect(32, 64, "full") == ((32.0, 64.0), (0.0, -32.0))

def test_collision_rect_none():
    assert _collision_rect(32, 64, "none") is None

def test_collision_rect_bottom():
    assert _collision_rect(32, 64, "bottom_16x16") == ((16.0, 16.0), (0.0, -8.0))
```

- [ ] **Step 5: Run all tests, verify pass**

Run: `uv run pytest art_source/pipeline/tests/test_godot_import.py -v`
Expected: all 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add art_source/pipeline/orchestrators/_godot_import.py art_source/pipeline/tests/test_godot_import.py
git commit -m "feat(pipeline): add shared Godot import helper module"
```

---

## Task 2: 擴展 manifest schema 追蹤 import 狀態

**Files:**
- Modify: `art_source/pipeline/manifest.py`

- [ ] **Step 1: Add import-state mutator functions**

Append after the existing `*_dir` helpers:

```python
def mark_imported(
    asset_type: str,
    name: str,
    *,
    game_png_path: str,
    game_tscn_path: str | None = None,
    game_json_path: str | None = None,
    collision: str | None = None,
) -> None:
    """Record that an asset has been copied into the Godot project tree."""
    from datetime import datetime
    fields: dict = {
        "imported_at": datetime.now().isoformat(timespec="seconds"),
        "game_png_path": game_png_path,
    }
    if game_tscn_path is not None:
        fields["game_tscn_path"] = game_tscn_path
    if game_json_path is not None:
        fields["game_json_path"] = game_json_path
    if collision is not None:
        fields["collision"] = collision

    if asset_type == "object":
        upsert_object(name=name, fields=fields)
    elif asset_type == "tileset":
        upsert_tileset(name=name, fields=fields)
    elif asset_type == "character":
        upsert_character(name=name, fields=fields)
    else:
        raise ValueError(f"unknown asset_type: {asset_type!r}")
```

- [ ] **Step 2: Verify imports compile**

Run: `uv run python -c "from art_source.pipeline import manifest; print(manifest.mark_imported)"`
Expected: prints `<function mark_imported at 0x...>`

- [ ] **Step 3: Commit**

```bash
git add art_source/pipeline/manifest.py
git commit -m "feat(pipeline): manifest tracks import state per asset"
```

---

## Task 3: 重寫 generate_spritesheet.py 為 per-character 模式

**Files:**
- Modify: `scripts/generate_spritesheet.py`

舊版讀 `art_source/characters/<name>/metadata.json` → 寫 `game/assets/spritesheet_cache/<name>.png` + 共享 `atlas_config.json`。

新版讀 art-pipeline 輸出 `art_source/pipeline/output/characters/<name>/animations/<action>/<dir>/frame_NNN.png` → 寫 `art_source/pipeline/output/characters/<name>/spritesheet/<name>.png` + `<name>.json` (per-character)。Godot 匯入由 orchestrator 階段負責。

- [ ] **Step 1: Replace `scripts/generate_spritesheet.py` (full rewrite)**

```python
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
```

- [ ] **Step 2: Smoke test on existing player character**

The old `art_source/characters/player` will be deleted in Task 8, so use a manually crafted fixture or skip. For now verify import succeeds:

Run: `uv run python -c "from scripts.generate_spritesheet import compile_character; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add scripts/generate_spritesheet.py
git commit -m "refactor: rewrite generate_spritesheet for per-character pipeline output"
```

---

## Task 4: prop.py 加 import_to_godot 階段

**Files:**
- Modify: `art_source/pipeline/orchestrators/prop.py`

- [ ] **Step 1: Add CLI flags + new stage**

Edit `prop.py`:

In `parse_args()`, add after `--category`:

```python
    p.add_argument("--collision", default="bottom_16x16",
                   help='碰撞範圍: none|bottom_16x8|bottom_16x16|full|"WxH"')
    p.add_argument("--no-collision", action="store_true",
                   help="不生成 StaticBody collision (覆蓋 --collision)")
```

In `STAGES`, change to:

```python
STAGES: list[str] = ["generate_object", "chroma_key", "import_to_godot"]
```

Update `chroma_key` decorator to `is_last=False`:

```python
@stage("chroma_key")
def chroma_key(ctx: StageContext) -> list[str]:
    ...
```

Add new stage before `main()`:

```python
@stage("import_to_godot", is_last=True)
def import_to_godot(ctx: StageContext) -> list[str]:
    from orchestrators import _godot_import as gimport
    args = ctx.args
    assert args is not None
    src = manifest.object_dir(ctx.name) / f"{ctx.name}.png"
    has_coll = not args.no_collision
    png_dest, tscn_dest = gimport.import_prop(
        src_png=src,
        name=ctx.name,
        collision=args.collision,
        has_collision=has_coll,
    )
    rel_root = plab.project_root()
    manifest.mark_imported(
        "object",
        ctx.name,
        game_png_path=str(png_dest.relative_to(rel_root)),
        game_tscn_path=str(tscn_dest.relative_to(rel_root)),
        collision=args.collision if has_coll else "none",
    )
    return [
        str(png_dest.relative_to(rel_root)),
        str(tscn_dest.relative_to(rel_root)),
    ]
```

In `main()`, add at end before final print:

```python
    import_to_godot(ctx)
```

- [ ] **Step 2: Smoke test the help text**

Run: `uv run python art_source/pipeline/orchestrators/prop.py --help`
Expected: `--collision`, `--no-collision` appear in help.

- [ ] **Step 3: Commit**

```bash
git add art_source/pipeline/orchestrators/prop.py
git commit -m "feat(prop): add import_to_godot stage"
```

---

## Task 5: autotile.py 加 import_to_godot 階段

**Files:**
- Modify: `art_source/pipeline/orchestrators/autotile.py`

- [ ] **Step 1: Inspect current STAGES list**

Run: `uv run grep -n "STAGES\|@stage" art_source/pipeline/orchestrators/autotile.py`

Note the last stage's name and `is_last=True`; it will need `is_last=False` after refactor.

- [ ] **Step 2: Append import_to_godot stage**

Add to STAGES list (append `"import_to_godot"`).
Change current last stage's decorator to `is_last=False`.
Add new stage:

```python
@stage("import_to_godot", is_last=True)
def import_to_godot(ctx: StageContext) -> list[str]:
    from orchestrators import _godot_import as gimport
    src = manifest.tileset_dir(ctx.name) / f"{ctx.name}_iso.png"
    if not src.exists():
        # fallback to whatever the previous stage produced
        candidates = sorted(manifest.tileset_dir(ctx.name).glob("*_iso.png"))
        if not candidates:
            raise SystemExit(f"no iso PNG found in {manifest.tileset_dir(ctx.name)}")
        src = candidates[-1]
    dest = gimport.import_tileset(src_png=src, name=ctx.name)
    rel_root = plab.project_root()
    manifest.mark_imported(
        "tileset",
        ctx.name,
        game_png_path=str(dest.relative_to(rel_root)),
    )
    return [str(dest.relative_to(rel_root))]
```

Add `import_to_godot(ctx)` call in `main()`.

- [ ] **Step 3: Smoke test help**

Run: `uv run python art_source/pipeline/orchestrators/autotile.py --help`
Expected: command runs without import errors.

- [ ] **Step 4: Commit**

```bash
git add art_source/pipeline/orchestrators/autotile.py
git commit -m "feat(autotile): add import_to_godot stage"
```

---

## Task 6: npc_static.py 與 npc_moving.py 加 import_to_godot 階段

**Files:**
- Modify: `art_source/pipeline/orchestrators/npc_static.py`
- Modify: `art_source/pipeline/orchestrators/npc_moving.py`

第一個改動: 修現有 `compile_spritesheet` 的破 CLI (`--character-dir` 旗標已在 Task 3 統一存在)。第二個改動: 加 import_to_godot stage。

- [ ] **Step 1: Modify `npc_static.py`**

Change `STAGES`:

```python
STAGES: list[str] = ["generate_4dir_base", "add_idle_animation", "compile_spritesheet", "import_to_godot"]
```

Change `compile_spritesheet` decorator to `is_last=False`.

Append new stage before `main()`:

```python
@stage("import_to_godot", is_last=True)
def import_to_godot(ctx: StageContext) -> list[str]:
    from orchestrators import _godot_import as gimport
    char_dir = manifest.character_dir(ctx.name)
    sheet_dir = char_dir / "spritesheet"
    src_png = sheet_dir / f"{ctx.name}.png"
    src_json = sheet_dir / f"{ctx.name}.json"
    if not src_png.exists() or not src_json.exists():
        raise SystemExit(
            f"spritesheet not found in {sheet_dir} — did compile_spritesheet succeed?"
        )
    png_dest, json_dest = gimport.import_character_spritesheet(
        src_png=src_png, src_atlas_json=src_json, name=ctx.name
    )
    rel_root = plab.project_root()
    manifest.mark_imported(
        "character",
        ctx.name,
        game_png_path=str(png_dest.relative_to(rel_root)),
        game_json_path=str(json_dest.relative_to(rel_root)),
    )
    return [
        str(png_dest.relative_to(rel_root)),
        str(json_dest.relative_to(rel_root)),
    ]
```

Add `import_to_godot(ctx)` call in `main()`.

- [ ] **Step 2: Apply identical changes to `npc_moving.py`**

Same delta — add to STAGES, flip current last to `is_last=False`, append new stage, call in `main()`.

- [ ] **Step 3: Smoke test both help screens**

Run:
```bash
uv run python art_source/pipeline/orchestrators/npc_static.py --help
uv run python art_source/pipeline/orchestrators/npc_moving.py --help
```
Expected: both run without import errors.

- [ ] **Step 4: Commit**

```bash
git add art_source/pipeline/orchestrators/npc_static.py art_source/pipeline/orchestrators/npc_moving.py
git commit -m "feat(npc): add import_to_godot stage to static + moving"
```

---

## Task 7: 更新 SpriteSheetLoader 路徑與 atlas schema

**Files:**
- Modify: `game/src/core/classes/SpriteSheetLoader.gd`

舊版讀 `res://assets/spritesheet_cache/atlas_config.json` (共享一份)。新版讀 `res://assets/textures/characters/<name>.json` (per-character),PNG 在同資料夾。

- [ ] **Step 1: Read existing file**

Run: `uv run grep -n "ATLAS_CONFIG\|SPRITESHEET_DIR\|_read_atlas_config\|load_character" game/src/core/classes/SpriteSheetLoader.gd`

- [ ] **Step 2: Replace path constants and config reader**

Edit `game/src/core/classes/SpriteSheetLoader.gd`:

Change:
```gdscript
const ATLAS_CONFIG: String = "res://assets/spritesheet_cache/atlas_config.json"
const SPRITESHEET_DIR: String = "res://assets/spritesheet_cache"
```
to:
```gdscript
const CHARACTERS_DIR: String = "res://assets/textures/characters"
```

Update `load_character(npc_id)`:
- Build `var sheet_path: String = "%s/%s.png" % [CHARACTERS_DIR, npc_id]`
- Build `var json_path: String = "%s/%s.json" % [CHARACTERS_DIR, npc_id]`
- Replace `_read_atlas_config()` calls with a per-character read returning the `animations` sub-dict.

Specifically, replace the body of `load_character` and `_read_atlas_config` so that `_read_atlas_config` takes `npc_id` and reads `<CHARACTERS_DIR>/<npc_id>.json`. Adjust callers accordingly.

(Implementer: do read the full existing file before editing. Treat this step as: "for each reference to ATLAS_CONFIG / SPRITESHEET_DIR, rewire to per-character path; for each `atlas[npc_id]` lookup, replace with `atlas` since the per-character JSON's top level IS that character's data.")

- [ ] **Step 3: Smoke test (manual, defer until Task 9 has at least one regenerated character)**

Mark this step DONE without testing — actual verification happens after a character is regenerated via the new pipeline.

- [ ] **Step 4: Commit**

```bash
git add game/src/core/classes/SpriteSheetLoader.gd
git commit -m "refactor(loader): per-character spritesheet + JSON, drop spritesheet_cache"
```

---

## Task 8: 刪除舊資產與舊腳本

不可逆操作 — 用戶已明確授權「除 iso_test 外既有素材全部重做」。

**Files (deletions):**
- `scripts/import_assets.py`
- `scripts/import-assets-guide.md`
- `game/assets/textures/environment/` (整個目錄,iso_test 不在此)
- `game/src/maps/props/urban/`
- `game/src/maps/props/nature/`
- `game/assets/spritesheet_cache/`
- `art_source/characters/`
- `temp/`

- [ ] **Step 1: Verify iso_test is NOT under environment/**

Run: `uv run python -c "from pathlib import Path; print(list(Path('game/assets/textures/environment').rglob('iso*')))"`
Expected: `[]`

If non-empty, STOP and report — iso_test must not be in the deleted tree.

- [ ] **Step 2: Verify zone scenes don't reference doomed paths (other than iso_test)**

Run: `uv run grep -rn "spritesheet_cache\|environment/props\|environment/tilesets\|maps/props/urban\|maps/props/nature" game/src/maps/ --include="*.tscn"`

Any matches in scenes other than `zone_iso_test.tscn` must be cleaned/recreated by user before deletion. If zone scenes reference these, list them in the commit message but proceed (user authorized the redo).

- [ ] **Step 3: Delete in one commit**

```powershell
Remove-Item -Recurse -Force scripts/import_assets.py, scripts/import-assets-guide.md
Remove-Item -Recurse -Force game/assets/textures/environment
Remove-Item -Recurse -Force game/src/maps/props/urban, game/src/maps/props/nature
Remove-Item -Recurse -Force game/assets/spritesheet_cache
Remove-Item -Recurse -Force art_source/characters
Remove-Item -Recurse -Force temp
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: drop legacy art pipeline (urban/nature props, spritesheet_cache, import_assets)"
```

---

## Task 9: 端到端煙霧測試 — 重生 player 角色

**Files:** none modified, only generates output.

驗證新 pipeline 能完整跑完並讓 Godot 載入。

- [ ] **Step 1: Re-init player in manifest (clean slate)**

Manually edit `art_source/pipeline/output/manifest.json`: delete the `characters.player` entry (or set status back to `init`), since the old character_id is from the old workflow.

- [ ] **Step 2: Run npc_moving for player**

Run with `--review-mode none` to go end-to-end (this consumes Pixellab credits and takes 15-30 min):

```powershell
uv run python art_source/pipeline/orchestrators/npc_moving.py `
  --name player `
  --description "young taiwanese male protagonist in his early 20s, short black hair, casual modern clothes (white t-shirt, dark jeans), small backpack, friendly and curious expression, slim athletic build" `
  --zone shared --category player `
  --review-mode none
```

Expected final state:
- `art_source/pipeline/output/characters/player/spritesheet/player.png` exists
- `game/assets/textures/characters/player.png` exists
- `game/assets/textures/characters/player.json` exists
- `manifest.json` has `characters.player.imported_at`

- [ ] **Step 3: Verify Godot can load the player**

Open Godot editor → press Ctrl+Shift+R → run `zone_iso_test` scene. Confirm player sprite renders (no missing-texture / atlas-key-not-found errors in Output panel).

If errors: re-read `SpriteSheetLoader.gd` against the actual `player.json` shape and fix mismatches.

- [ ] **Step 4: Commit if any fixes were needed; otherwise skip**

---

## Task 10: 更新文檔與 memory

**Files:**
- Modify: `.claude/skills/art-pipeline/SKILL.md` (or wherever the skill content lives)
- Modify: `docs/INDEX.md`
- Modify: `docs/asset-naming-convention.md`
- Modify: `docs/scene-design-workflow.md`
- Modify: `~/.claude/projects/<...>/memory/MEMORY.md`
- Modify: memory entry for asset import workflow

- [ ] **Step 1: Locate current skill file**

Run: `uv run grep -rn "import_assets.py\|spritesheet_cache\|urban|nature" .claude/skills/ docs/`

- [ ] **Step 2: Update skill / docs in place**

For every reference to the deleted artefacts, replace with the new flow:
- `scripts/import_assets.py` → "deprecated; use orchestrator's `import_to_godot` stage"
- `spritesheet_cache/` → `assets/textures/characters/`
- `urban|nature`分類 → "扁平結構,以 manifest tag 過濾"

Update `art-pipeline/SKILL.md` STAGES tables to include `import_to_godot` at the end of each pipeline.
Add note in CLI examples that the final stage auto-imports — `--review-mode stage` stops before import.
Add `--collision` flag to prop examples.

- [ ] **Step 3: Rewrite the asset-import memory entry**

Edit `~/.claude/projects/c--Users-Justin-Documents-GitHub-MuzhaRPG-Project/memory/feedback_asset_import_workflow.md`:

```markdown
---
name: 美術素材匯入由 orchestrator 自動完成
description: pipeline orchestrator 終端 stage `import_to_godot` 自動把產物搬進 Godot,不再有 import_assets.py
type: feedback
---
art pipeline 的 4 個 orchestrator (prop / autotile / npc_static / npc_moving) 都以 `import_to_godot` 為最後一個 stage,自動完成 Godot 端的 PNG 複製 + .tscn 生成 + manifest 更新。

**Why:** 舊雙工具流程 (生圖 → 手動跑 import_assets.py) 兩邊 manifest 互不相通,且 `category` 一字在兩邊意義不同,易踩坑。已於 2026-05-05 統一。

**How to apply:** 看到使用者要新美術資產一律走 orchestrator (Bash 呼叫 `art_source/pipeline/orchestrators/*.py`),不要找 `scripts/import_assets.py` (已刪)。`--review-mode stage` 會在 import 前停下讓人檢查中間產物。
```

Update `MEMORY.md` index line accordingly.

- [ ] **Step 4: Commit**

```bash
git add docs/ .claude/skills/
git commit -m "docs: update art pipeline docs + skill for unified import flow"
```

Memory updates are outside the repo — apply directly via Write tool, no commit.

---

## Self-Review Checklist

- [x] Spec coverage: all 4 confirmed decisions (拿掉 environment/、保留 portraits 與 characters 分開、原料留 art_source、自動匯入) are addressed across Tasks 1-10.
- [x] Placeholder scan: no TBDs. Task 7 step 2 has prose-style instruction for SpriteSheetLoader rewrite — flagged, not handwaved (full file must be read first).
- [x] Type consistency: `import_prop` / `import_tileset` / `import_character_spritesheet` signatures used in Tasks 1, 4, 5, 6 match. `mark_imported` keyword args (`game_png_path`, `game_tscn_path`, `game_json_path`, `collision`) are consistent across callers.
- [x] Single source of truth: `manifest.json` extended (Task 2), every import stage writes via `mark_imported` (Tasks 4-6).

## Out of scope

- Migrating existing player/NPC characters (user authorized full redo via Task 9).
- TileMapDual TileSet `.tres` generation (autotile import only copies PNG; .tres setup is human work in Godot editor per `docs/tilemapdual-guide.md`).
- Updating `zone_market.tscn` and other zone scenes — they will need manual rebuild after their referenced props are regenerated, but that's a content task, not pipeline.
