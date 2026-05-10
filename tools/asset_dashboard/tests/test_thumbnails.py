# tools/asset_dashboard/tests/test_thumbnails.py
from pathlib import Path

from tools.asset_dashboard.backend.thumbnails import resolve_thumbnail


def test_resolve_thumbnail_character_uses_south_rotation(tmp_path):
    char_dir = tmp_path / "art_source/pipeline/output/characters/alice"
    rot = char_dir / "rotations"
    rot.mkdir(parents=True)
    south = rot / "south.png"
    south.write_bytes(b"\x89PNG fake")
    result = resolve_thumbnail(tmp_path, "character", "alice", entry={})
    assert result == south


def test_resolve_thumbnail_object_uses_object_png(tmp_path):
    obj_dir = tmp_path / "art_source/pipeline/output/objects/lantern"
    obj_dir.mkdir(parents=True)
    png = obj_dir / "lantern.png"
    png.write_bytes(b"\x89PNG fake")
    result = resolve_thumbnail(tmp_path, "object", "lantern", entry={})
    assert result == png


def test_resolve_thumbnail_tileset_uses_iso_png(tmp_path):
    tileset_dir = tmp_path / "art_source/pipeline/output/tilesets/grass_dirt"
    tileset_dir.mkdir(parents=True)
    png = tileset_dir / "grass_dirt_iso.png"
    png.write_bytes(b"\x89PNG fake")
    result = resolve_thumbnail(tmp_path, "tileset", "grass_dirt", entry={})
    assert result == png


def test_resolve_thumbnail_returns_none_when_missing(tmp_path):
    result = resolve_thumbnail(tmp_path, "character", "ghost", entry={})
    assert result is None
