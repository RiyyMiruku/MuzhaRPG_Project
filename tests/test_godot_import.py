from pathlib import Path

from orchestrators._godot_import import godot_uid


def test_godot_uid_deterministic():
    assert godot_uid("tex:lantern_red") == godot_uid("tex:lantern_red")

def test_godot_uid_format():
    uid = godot_uid("tex:lantern_red")
    assert uid.startswith("uid://c")
    assert len(uid) == len("uid://c") + 13

def test_godot_uid_distinct():
    assert godot_uid("a") != godot_uid("b")


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


from PIL import Image as _Image

from orchestrators._godot_import import (
    import_prop,
    import_tileset,
    import_character_spritesheet,
)


def _make_test_png(path: Path, size: tuple[int, int] = (32, 32)) -> None:
    img = _Image.new("RGBA", size, (255, 0, 0, 255))
    img.save(path)


def test_import_prop_with_collision(tmp_path):
    src = tmp_path / "src" / "world_tree.png"
    src.parent.mkdir()
    _make_test_png(src, (64, 64))

    png_dest, tscn_dest = import_prop(
        src_png=src, name="world_tree",
        collision="bottom_16x16", has_collision=True,
        root=tmp_path,
    )
    assert png_dest == tmp_path / "game/assets/textures/props/world_tree.png"
    assert tscn_dest == tmp_path / "game/src/maps/props/world_tree.tscn"
    assert png_dest.exists()
    assert tscn_dest.exists()
    body = tscn_dest.read_text(encoding="utf-8")
    assert "load_steps=5" in body
    assert 'instance=ExtResource("4_tmpl")' in body
    assert 'has_collision = true' in body
    assert 'RectangleShape2D' in body
    # texture ext_resource has both uid and path
    assert 'type="Texture2D" uid="uid://c' in body
    assert 'path="res://assets/textures/props/world_tree.png"' in body


def test_import_prop_no_collision(tmp_path):
    src = tmp_path / "src" / "lantern_red.png"
    src.parent.mkdir()
    _make_test_png(src, (32, 32))

    png_dest, tscn_dest = import_prop(
        src_png=src, name="lantern_red",
        collision="none", has_collision=False,
        root=tmp_path,
    )
    body = tscn_dest.read_text(encoding="utf-8")
    assert "load_steps=4" in body
    assert 'has_collision = false' in body


def test_import_tileset(tmp_path):
    src = tmp_path / "src" / "grass_iso.png"
    src.parent.mkdir()
    _make_test_png(src)
    dest = import_tileset(src_png=src, name="market_grass_asphalt", root=tmp_path)
    assert dest == tmp_path / "game/assets/textures/tilesets/market_grass_asphalt.png"
    assert dest.exists()


def test_import_character_spritesheet(tmp_path):
    src_png = tmp_path / "src" / "player.png"
    src_json = tmp_path / "src" / "player.json"
    src_png.parent.mkdir()
    _make_test_png(src_png, (368, 184))
    src_json.write_text('{"character_name":"player","frame_size":[92,92],"animations":{}}', encoding="utf-8")

    png_dest, json_dest = import_character_spritesheet(
        src_png=src_png, src_atlas_json=src_json, name="player", root=tmp_path,
    )
    assert png_dest == tmp_path / "game/assets/textures/characters/player.png"
    assert json_dest == tmp_path / "game/assets/textures/characters/player.json"
    assert png_dest.exists()
    assert json_dest.exists()
