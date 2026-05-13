"""
Manifest 管理 — 本地索引所有透過 pipeline 產出的美術資產。

**v2 (2026-05-14)**: 從單一 art_source/manifest.json 改成「每資產一個
asset.json」(file-per-asset)。Public API 完全不變,callers 不需修改。

每資產一個檔案的好處:
  - 寫入只影響該資產的 asset.json,實體上不可能 race condition (取代 fcntl)
  - git diff 漂亮,改一個資產動一個檔
  - 移動/備份單一資產 = 移動/備份單一目錄
  - manifest schema 向前演進無痛 (read-time forgive missing fields)

Reading "整個 manifest" 走 load(),會 walk art_source/ 下所有 asset.json
重組成跟舊版相同的 {characters, tilesets, objects} 字典結構,所以 caller
只看到行為等價。

設計細節見 docs/archive/2026-05-pipeline-v2-design.md。

== 資產 layout ==

  art_source/
  ├── characters/
  │   ├── player/
  │   │   ├── asset.json         ← 此檔案 (metadata)
  │   │   ├── rotations/
  │   │   └── spritesheet/
  │   └── ...
  ├── objects/
  │   └── <name>/
  │       ├── asset.json
  │       └── <name>.png
  └── tilesets/
      └── <name>/
          ├── asset.json
          └── <name>_iso.png
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
from pathlib import Path
from typing import Any


MANIFEST_VERSION: int = 2  # bumped: per-asset file layout


# === Naming convention ===


NAME_PATTERN: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")
NAME_MIN_LEN: int = 3
NAME_MAX_LEN: int = 64


def validate_asset_name(name: str) -> None:
    """檢查 asset name 是否符合命名規範。違規 raise ValueError。

    規則:
      - 純小寫 ASCII + 數字 + 底線
      - 開頭必須是字母,結尾必須是字母或數字
      - 不能有連續底線(__)
      - 長度 3-64
    """
    if not isinstance(name, str):
        raise ValueError(f"name 必須是 str,收到 {type(name).__name__}")
    if not (NAME_MIN_LEN <= len(name) <= NAME_MAX_LEN):
        raise ValueError(
            f"name '{name}' 長度 {len(name)} 不在 {NAME_MIN_LEN}-{NAME_MAX_LEN}"
        )
    if not NAME_PATTERN.fullmatch(name):
        raise ValueError(
            f"name '{name}' 不符合命名規範:純小寫字母/數字/底線,"
            f"字母開頭,字母或數字結尾,無連續底線。詳見 "
            f"docs/asset-naming-convention.md"
        )


# === Path helpers ===


def output_dir() -> Path:
    """art_source/ 根目錄。"""
    return Path(__file__).resolve().parent.parent / "art_source"


def manifest_path() -> Path:
    """legacy aggregate file path. v2 起不再寫入此檔,但保留供以下用途:
      - 遷移腳本知道從哪讀舊資料
      - 測試 fixture monkeypatch (見 tests/conftest.py)
      - 任何外部工具還在 grep 此路徑時不出錯
    """
    return output_dir() / "manifest.json"


def character_dir(name: str) -> Path:
    return output_dir() / "characters" / name


def tileset_dir(name: str) -> Path:
    return output_dir() / "tilesets" / name


def object_dir(name: str) -> Path:
    return output_dir() / "objects" / name


# === Asset type → directory mapping ===


_ASSET_KEY: dict[str, str] = {
    "character": "characters",
    "tileset": "tilesets",
    "object": "objects",
}

_BUCKET_TO_TYPE: dict[str, str] = {v: k for k, v in _ASSET_KEY.items()}


def _bucket_for(asset_type: str) -> str:
    if asset_type not in _ASSET_KEY:
        raise ValueError(f"unknown asset_type: {asset_type!r}")
    return _ASSET_KEY[asset_type]


def _type_dir(bucket: str) -> Path:
    return output_dir() / bucket


# === Per-asset file IO ===


def _asset_file(bucket: str, name: str) -> Path:
    return _type_dir(bucket) / name / "asset.json"


def _read_asset(bucket: str, name: str) -> dict[str, Any] | None:
    p = _asset_file(bucket, name)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def _write_asset(bucket: str, name: str, entry: dict[str, Any]) -> None:
    """Atomic write of a single asset.json via temp file + rename.

    No fcntl lock needed: each asset has its own file, two writers to
    different assets cannot collide; two writers to the SAME asset is a
    bug elsewhere (the same orchestrator should not be running twice).
    """
    p = _asset_file(bucket, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)


def _delete_asset_file(bucket: str, name: str) -> bool:
    """Remove just the asset.json (not the asset's image files / rotations).
    Returns False if file didn't exist."""
    p = _asset_file(bucket, name)
    if not p.exists():
        return False
    p.unlink()
    return True


def _iter_assets(bucket: str) -> "dict[str, dict[str, Any]]":
    """Walk art_source/<bucket>/*/asset.json → {name: entry}.

    Skips directories without an asset.json (e.g., orphan rotations from
    a crashed run that never got registered).
    """
    out: dict[str, dict[str, Any]] = {}
    base = _type_dir(bucket)
    if not base.exists():
        return out
    for asset_dir in sorted(base.iterdir()):
        if not asset_dir.is_dir():
            continue
        f = asset_dir / "asset.json"
        if not f.exists():
            continue
        try:
            out[asset_dir.name] = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            # Surface bad asset.json early instead of silently dropping.
            raise RuntimeError(f"invalid asset.json at {f}: {e}") from e
    return out


def _empty_manifest() -> dict[str, Any]:
    return {
        "version": MANIFEST_VERSION,
        "characters": {},
        "tilesets": {},
        "objects": {},
    }


# === Aggregate read (back-compat for `load()` callers) ===


def load() -> dict[str, Any]:
    """Aggregate read: rebuild the legacy {characters, tilesets, objects}
    dict by walking all per-asset asset.json files.

    Cost ≤ 50 ms for 500 assets (small JSON files, sequential read);
    well under any UI / CLI tolerance. If this becomes a hotspot we can
    add a cached aggregate file rebuilt on writes — but YAGNI for now.
    """
    return {
        "version": MANIFEST_VERSION,
        "characters": _iter_assets("characters"),
        "tilesets": _iter_assets("tilesets"),
        "objects": _iter_assets("objects"),
    }


def save(data: dict[str, Any]) -> None:
    """**Migration-only path**. Splits an aggregate dict into per-asset
    asset.json files.

    Normal callers should use upsert_* / mark_stage / etc., which write
    only the affected asset's file. Calling save(load() + tweak) is
    wasteful but functionally correct.
    """
    for bucket in ("characters", "tilesets", "objects"):
        for name, entry in (data.get(bucket) or {}).items():
            _write_asset(bucket, name, entry)


def now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


# === Asset CRUD ===


def _upsert_in_bucket(bucket: str, name: str, fields: dict[str, Any]) -> None:
    existing = _read_asset(bucket, name) or {}
    existing.update(fields)
    existing.setdefault("created_at", now_iso())
    existing["updated_at"] = now_iso()
    _write_asset(bucket, name, existing)


def upsert_character(name: str, fields: dict[str, Any]) -> None:
    """新增或更新角色條目。fields 會 merge 進現有資料,不覆蓋未指定欄位。"""
    _upsert_in_bucket("characters", name, fields)


def upsert_tileset(name: str, fields: dict[str, Any]) -> None:
    _upsert_in_bucket("tilesets", name, fields)


def upsert_object(name: str, fields: dict[str, Any]) -> None:
    _upsert_in_bucket("objects", name, fields)


def get_character(name: str) -> dict[str, Any] | None:
    return _read_asset("characters", name)


def get_tileset(name: str) -> dict[str, Any] | None:
    return _read_asset("tilesets", name)


def get_object(name: str) -> dict[str, Any] | None:
    return _read_asset("objects", name)


def remove_character(name: str) -> bool:
    return _delete_asset_file("characters", name)


def remove_tileset(name: str) -> bool:
    return _delete_asset_file("tilesets", name)


def remove_object(name: str) -> bool:
    return _delete_asset_file("objects", name)


# === Stage tracking ===


def add_tags(asset_type: str, name: str, new_tags: list[str]) -> None:
    """加 tag 到資產(去重保序)。"""
    bucket = _bucket_for(asset_type)
    entry = _read_asset(bucket, name)
    if entry is None:
        raise KeyError(f"{asset_type} '{name}' not found in manifest")
    existing: list[str] = entry.setdefault("tags", [])
    for t in new_tags:
        if t and t not in existing:
            existing.append(t)
    entry["updated_at"] = now_iso()
    _write_asset(bucket, name, entry)


def query_assets(
    asset_type: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """查資產:依 type/tags 過濾。

    asset_type=None → 跨所有 type
    tags=None or [] → 不過濾;否則所有 tag 都必須在 entry.tags 中(AND 邏輯)
    回傳 {full_name: entry},full_name 格式 "<type>:<name>" 避免跨 type 撞名
    """
    if asset_type is not None and asset_type not in _ASSET_KEY:
        raise ValueError(f"unknown asset_type: {asset_type}")
    types = [asset_type] if asset_type else list(_ASSET_KEY.keys())
    out: dict[str, dict[str, Any]] = {}
    for t in types:
        bucket = _ASSET_KEY[t]
        for name, entry in _iter_assets(bucket).items():
            if tags:
                entry_tags = set(entry.get("tags", []))
                if not all(tag in entry_tags for tag in tags):
                    continue
            out[f"{t}:{name}"] = entry
    return out


def mark_stage(
    asset_type: str,
    name: str,
    stage_name: str,
    paths: list[str],
) -> None:
    """記錄某資產某 stage 已完成,寫入 asset.json。

    重複呼叫同一 stage_name 會覆蓋既有 completed_at 與 paths
    (供 @stage decorator 的 --force-restart-stage 流程使用)。
    """
    bucket = _bucket_for(asset_type)
    entry = _read_asset(bucket, name)
    if entry is None:
        raise KeyError(f"{asset_type} '{name}' not found in manifest")
    stages = entry.setdefault("stages", {})
    stages[stage_name] = {
        "completed_at": now_iso(),
        "paths": paths,
    }
    entry["updated_at"] = now_iso()
    _write_asset(bucket, name, entry)


def get_completed_stages(asset_type: str, name: str) -> list[str]:
    """回傳已完成 stage 名,依寫入順序。"""
    bucket = _bucket_for(asset_type)
    entry = _read_asset(bucket, name) or {}
    return list((entry.get("stages") or {}).keys())


# === Import-state tracking ===


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
    fields: dict = {
        "imported_at": now_iso(),
        "game_png_path": game_png_path,
    }
    if game_tscn_path is not None:
        fields["game_tscn_path"] = game_tscn_path
    if game_json_path is not None:
        fields["game_json_path"] = game_json_path
    if collision is not None:
        fields["collision"] = collision
    _upsert_in_bucket(_bucket_for(asset_type), name, fields)


# === Prompt management ===


def get_prompt(asset_type: str, name: str, stage: str) -> str | None:
    """讀指定 stage 的 prompt。falls back 到 description (stage 1 兼容舊資產)。"""
    bucket = _bucket_for(asset_type)
    entry = _read_asset(bucket, name)
    if entry is None:
        return None
    prompts = entry.get("prompts") or {}
    if stage in prompts:
        return prompts[stage]
    if stage in {"generate_8dir_base", "generate_4dir_base", "generate_object", "generate_atlas"}:
        return entry.get("description")
    return None


def list_prompts(asset_type: str, name: str) -> dict[str, str]:
    """回傳該資產所有已存的 prompts (不含 description fallback)。"""
    bucket = _bucket_for(asset_type)
    entry = _read_asset(bucket, name) or {}
    return dict(entry.get("prompts") or {})


def set_prompt(asset_type: str, name: str, stage: str, prompt: str) -> None:
    """寫入指定 stage 的 prompt。資產必須已存在。"""
    bucket = _bucket_for(asset_type)
    entry = _read_asset(bucket, name)
    if entry is None:
        raise KeyError(f"{asset_type} {name!r} not in manifest")
    prompts = dict(entry.get("prompts") or {})
    prompts[stage] = prompt
    entry["prompts"] = prompts
    entry["updated_at"] = now_iso()
    _write_asset(bucket, name, entry)
