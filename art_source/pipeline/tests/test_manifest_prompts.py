from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import manifest


def test_get_prompt_returns_stored(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "manifest_path", lambda: tmp_path / "m.json")
    manifest.save(
        {
            "version": 1,
            "characters": {
                "alice": {
                    "description": "fallback text",
                    "prompts": {"generate_8dir_base": "explicit"},
                }
            },
            "tilesets": {},
            "objects": {},
        }
    )
    assert manifest.get_prompt("character", "alice", "generate_8dir_base") == "explicit"


def test_get_prompt_falls_back_to_description(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "manifest_path", lambda: tmp_path / "m.json")
    manifest.save(
        {
            "version": 1,
            "characters": {
                "alice": {"description": "old style", "prompts": {}},
            },
            "tilesets": {},
            "objects": {},
        }
    )
    assert manifest.get_prompt("character", "alice", "generate_8dir_base") == "old style"


def test_get_prompt_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "manifest_path", lambda: tmp_path / "m.json")
    manifest.save(
        {
            "version": 1,
            "characters": {"alice": {}},
            "tilesets": {},
            "objects": {},
        }
    )
    assert manifest.get_prompt("character", "alice", "add_idle_animation") is None


def test_set_prompt_writes_through(tmp_path, monkeypatch):
    mpath = tmp_path / "m.json"
    monkeypatch.setattr(manifest, "manifest_path", lambda: mpath)
    manifest.save(
        {
            "version": 1,
            "characters": {"alice": {}},
            "tilesets": {},
            "objects": {},
        }
    )
    manifest.set_prompt("character", "alice", "add_idle_animation", "smoking calmly")
    data = json.loads(mpath.read_text(encoding="utf-8"))
    assert data["characters"]["alice"]["prompts"]["add_idle_animation"] == "smoking calmly"


def test_list_prompts_for_asset(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "manifest_path", lambda: tmp_path / "m.json")
    manifest.save(
        {
            "version": 1,
            "characters": {
                "alice": {
                    "description": "base",
                    "prompts": {"add_idle_animation": "idle calm"},
                }
            },
            "tilesets": {},
            "objects": {},
        }
    )
    prompts = manifest.list_prompts("character", "alice")
    assert prompts == {"add_idle_animation": "idle calm"}


def test_set_prompt_unknown_asset_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "manifest_path", lambda: tmp_path / "m.json")
    manifest.save(
        {"version": 1, "characters": {}, "tilesets": {}, "objects": {}}
    )
    import pytest

    with pytest.raises(KeyError):
        manifest.set_prompt("character", "nobody", "stage", "x")
