"""
Manifest 管理 — 本地索引所有透過 pipeline 產出的美術資產。

讓使用者只需用「名字」就能操作資產（例：animate_character("chen_ayi", "walk")），
不必記 Pixellab 後端的 UUID。

manifest.json 結構：
{
  "version": 1,
  "characters": { "<name>": { character_id, preset, view, ... } },
  "tilesets":   { "<name>": { tileset_id, lower, upper, ... } },
  "objects":    { "<name>": { object_id, view, ... } }
}
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path
from typing import Any


MANIFEST_VERSION: int = 1


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


def manifest_path() -> Path:
    """art_source/pipeline/output/manifest.json 的絕對路徑。"""
    return Path(__file__).resolve().parent / "output" / "manifest.json"


def _empty_manifest() -> dict[str, Any]:
    return {
        "version": MANIFEST_VERSION,
        "characters": {},
        "tilesets": {},
        "objects": {},
    }


def load() -> dict[str, Any]:
    """載入 manifest，不存在則回傳空骨架。"""
    p = manifest_path()
    if not p.exists():
        return _empty_manifest()
    return json.loads(p.read_text(encoding="utf-8"))


def save(data: dict[str, Any]) -> None:
    """寫回 manifest（覆蓋），自動 mkdir。"""
    p = manifest_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


# === Asset CRUD ===


def upsert_character(name: str, fields: dict[str, Any]) -> None:
    """新增或更新角色條目。fields 會 merge 進現有資料，不覆蓋未指定欄位。"""
    data = load()
    existing: dict[str, Any] = data["characters"].get(name, {})
    existing.update(fields)
    existing.setdefault("created_at", now_iso())
    existing["updated_at"] = now_iso()
    data["characters"][name] = existing
    save(data)


def upsert_tileset(name: str, fields: dict[str, Any]) -> None:
    data = load()
    existing: dict[str, Any] = data["tilesets"].get(name, {})
    existing.update(fields)
    existing.setdefault("created_at", now_iso())
    existing["updated_at"] = now_iso()
    data["tilesets"][name] = existing
    save(data)


def upsert_object(name: str, fields: dict[str, Any]) -> None:
    data = load()
    existing: dict[str, Any] = data["objects"].get(name, {})
    existing.update(fields)
    existing.setdefault("created_at", now_iso())
    existing["updated_at"] = now_iso()
    data["objects"][name] = existing
    save(data)


def get_character(name: str) -> dict[str, Any] | None:
    return load()["characters"].get(name)


def get_tileset(name: str) -> dict[str, Any] | None:
    return load()["tilesets"].get(name)


def get_object(name: str) -> dict[str, Any] | None:
    return load()["objects"].get(name)


def remove_character(name: str) -> bool:
    data = load()
    if name not in data["characters"]:
        return False
    del data["characters"][name]
    save(data)
    return True


def remove_tileset(name: str) -> bool:
    data = load()
    if name not in data["tilesets"]:
        return False
    del data["tilesets"][name]
    save(data)
    return True


def remove_object(name: str) -> bool:
    data = load()
    if name not in data["objects"]:
        return False
    del data["objects"][name]
    save(data)
    return True


# === Stage tracking ===


_ASSET_KEY: dict[str, str] = {
    "character": "characters",
    "tileset": "tilesets",
    "object": "objects",
}


def add_tags(asset_type: str, name: str, new_tags: list[str]) -> None:
    """加 tag 到資產(去重保序)。asset_type 用 _ASSET_KEY 既有 mapping。"""
    key = _ASSET_KEY.get(asset_type)
    if key is None:
        raise ValueError(f"unknown asset_type: {asset_type}")
    data = load()
    if name not in data[key]:
        raise KeyError(f"{asset_type} '{name}' not found in manifest")
    entry = data[key][name]
    existing: list[str] = entry.setdefault("tags", [])
    for t in new_tags:
        if t and t not in existing:
            existing.append(t)
    entry["updated_at"] = now_iso()
    save(data)


def query_assets(
    asset_type: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """查資產:依 type/tags 過濾。

    asset_type=None → 跨所有 type
    tags=None or [] → 不過濾;否則所有 tag 都必須在 entry.tags 中(AND 邏輯)
    回傳 {full_name: entry},full_name 格式 "<type>:<name>" 避免跨 type 撞名
    """
    data = load()
    if asset_type is not None and asset_type not in _ASSET_KEY:
        raise ValueError(f"unknown asset_type: {asset_type}")
    types = [asset_type] if asset_type else list(_ASSET_KEY.keys())
    out: dict[str, dict[str, Any]] = {}
    for t in types:
        key = _ASSET_KEY[t]
        for name, entry in data[key].items():
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
    """記錄某資產某 stage 已完成,寫入 manifest。

    asset_type: "character" | "tileset" | "object"
    paths: 該 stage 產出的檔案路徑(相對 project root)

    重複呼叫同一 stage_name 會覆蓋既有 completed_at 與 paths
    (供 Task 5 @stage decorator 的 --force-restart-stage 流程使用)。
    """
    key = _ASSET_KEY.get(asset_type)
    if key is None:
        raise ValueError(f"unknown asset_type: {asset_type}")
    data = load()
    if name not in data[key]:
        raise KeyError(f"{asset_type} '{name}' not found in manifest")
    entry = data[key][name]
    stages = entry.setdefault("stages", {})
    stages[stage_name] = {
        "completed_at": now_iso(),
        "paths": paths,
    }
    entry["updated_at"] = now_iso()
    save(data)


def get_completed_stages(asset_type: str, name: str) -> list[str]:
    """回傳已完成 stage 名,依 manifest 寫入順序。"""
    key = _ASSET_KEY.get(asset_type)
    if key is None:
        raise ValueError(f"unknown asset_type: {asset_type}")
    data = load()
    entry = data[key].get(name, {})
    stages = entry.get("stages", {})
    return list(stages.keys())


# === 路徑 helpers ===


def output_dir() -> Path:
    return Path(__file__).resolve().parent / "output"


def character_dir(name: str) -> Path:
    return output_dir() / "characters" / name


def tileset_dir(name: str) -> Path:
    return output_dir() / "tilesets" / name


def object_dir(name: str) -> Path:
    return output_dir() / "objects" / name
