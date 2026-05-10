# tools/asset_dashboard/tests/test_manifest_io.py
import json
from pathlib import Path

import pytest

from tools.asset_dashboard.backend.manifest_io import (
    load_assets,
    AssetSummary,
)


def _write_manifest(path: Path, content: dict) -> None:
    path.write_text(json.dumps(content), encoding="utf-8")


def test_load_assets_returns_one_asset_per_entry(tmp_path):
    mpath = tmp_path / "manifest.json"
    _write_manifest(mpath, {
        "version": 1,
        "characters": {
            "alice": {
                "description": "alice the witch",
                "tags": ["zone:nccu", "chapter:1"],
                "stages": {"generate_8dir_base": {"completed_at": "2026-01-01"}},
                "prompts": {"add_idle_animation": "casting"},
            }
        },
        "tilesets": {
            "grass_to_dirt": {
                "description": "natural transition",
                "tags": ["zone:market"],
                "stages": {},
            }
        },
        "objects": {},
    })

    assets = load_assets(mpath)
    assert len(assets) == 2
    by_name = {a.name: a for a in assets}
    assert by_name["alice"].asset_type == "character"
    assert by_name["alice"].chapter == "1"
    assert by_name["alice"].zone == "nccu"
    assert by_name["alice"].completed_stages == ["generate_8dir_base"]
    assert by_name["alice"].prompts == {"add_idle_animation": "casting"}
    assert by_name["grass_to_dirt"].asset_type == "tileset"
    assert by_name["grass_to_dirt"].chapter is None


def test_load_assets_handles_missing_optional_fields(tmp_path):
    mpath = tmp_path / "manifest.json"
    _write_manifest(mpath, {
        "version": 1,
        "characters": {"bob": {}},
        "tilesets": {},
        "objects": {},
    })
    assets = load_assets(mpath)
    assert len(assets) == 1
    a = assets[0]
    assert a.name == "bob"
    assert a.tags == []
    assert a.completed_stages == []
    assert a.prompts == {}


def test_asset_summary_serializes_to_dict():
    s = AssetSummary(
        name="alice",
        asset_type="character",
        description="x",
        tags=["zone:a", "chapter:2"],
        zone="a",
        category=None,
        chapter="2",
        completed_stages=["s1"],
        all_stages=["s1", "s2"],
        prompts={"s1": "p1"},
        png_path=None,
    )
    d = s.to_dict()
    assert d["name"] == "alice"
    assert d["chapter"] == "2"
    assert d["progress"] == "1/2"
