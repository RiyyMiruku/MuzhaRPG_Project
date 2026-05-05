"""Tests for manifest stage tracking."""
from __future__ import annotations

from pathlib import Path

import manifest


def test_mark_stage_writes_to_manifest(isolated_manifest: Path) -> None:
    manifest.upsert_character("alice", {"character_id": "uuid-1"})
    manifest.mark_stage(
        asset_type="character",
        name="alice",
        stage_name="generate_8dir_base",
        paths=["characters/alice/rotations/south.png"],
    )
    char = manifest.get_character("alice")
    assert char is not None
    stages = char["stages"]
    assert "generate_8dir_base" in stages
    assert stages["generate_8dir_base"]["paths"] == [
        "characters/alice/rotations/south.png"
    ]
    assert "completed_at" in stages["generate_8dir_base"]


def test_get_completed_stages_empty(isolated_manifest: Path) -> None:
    manifest.upsert_character("bob", {"character_id": "uuid-2"})
    assert manifest.get_completed_stages("character", "bob") == []


def test_get_completed_stages_returns_names_in_order(isolated_manifest: Path) -> None:
    manifest.upsert_character("carol", {"character_id": "uuid-3"})
    manifest.mark_stage("character", "carol", "stage_a", ["p1"])
    manifest.mark_stage("character", "carol", "stage_b", ["p2"])
    completed = manifest.get_completed_stages("character", "carol")
    assert completed == ["stage_a", "stage_b"]


def test_mark_stage_unknown_asset_type_raises(isolated_manifest: Path) -> None:
    import pytest
    with pytest.raises(ValueError, match="unknown asset_type"):
        manifest.mark_stage("widget", "x", "s", [])


def test_mark_stage_unknown_name_raises(isolated_manifest: Path) -> None:
    import pytest
    with pytest.raises(KeyError, match="not found"):
        manifest.mark_stage("character", "ghost", "s", [])
