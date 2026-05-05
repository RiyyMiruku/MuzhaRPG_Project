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
from pathlib import Path
from typing import Any


MANIFEST_VERSION: int = 1


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


# === 路徑 helpers ===


def output_dir() -> Path:
    return Path(__file__).resolve().parent / "output"


def character_dir(name: str) -> Path:
    return output_dir() / "characters" / name


def tileset_dir(name: str) -> Path:
    return output_dir() / "tilesets" / name


def object_dir(name: str) -> Path:
    return output_dir() / "objects" / name
