"""Tests for manifest prompt CRUD.

These tests use the `isolated_manifest` fixture (see tests/conftest.py) which
monkeypatches BOTH `manifest_path` and `output_dir` to a tmp_path, so v2
per-asset files don't leak into the real art_source/ tree.
"""
import manifest


def test_get_prompt_returns_stored(isolated_manifest):
    manifest.upsert_character("alice", {
        "description": "fallback text",
        "prompts": {"generate_8dir_base": "explicit"},
    })
    assert manifest.get_prompt("character", "alice", "generate_8dir_base") == "explicit"


def test_get_prompt_falls_back_to_description(isolated_manifest):
    manifest.upsert_character("alice", {"description": "old style", "prompts": {}})
    assert manifest.get_prompt("character", "alice", "generate_8dir_base") == "old style"


def test_get_prompt_missing_returns_none(isolated_manifest):
    manifest.upsert_character("alice", {})
    assert manifest.get_prompt("character", "alice", "add_idle_animation") is None


def test_set_prompt_writes_through(isolated_manifest):
    manifest.upsert_character("alice", {})
    manifest.set_prompt("character", "alice", "add_idle_animation", "smoking calmly")
    # Read back via the public API rather than reaching into the file format.
    assert manifest.list_prompts("character", "alice") == {
        "add_idle_animation": "smoking calmly",
    }


def test_list_prompts_for_asset(isolated_manifest):
    manifest.upsert_character("alice", {
        "description": "base",
        "prompts": {"add_idle_animation": "idle calm"},
    })
    assert manifest.list_prompts("character", "alice") == {"add_idle_animation": "idle calm"}


def test_set_prompt_unknown_asset_raises(isolated_manifest):
    import pytest
    with pytest.raises(KeyError):
        manifest.set_prompt("character", "nobody", "stage", "x")
