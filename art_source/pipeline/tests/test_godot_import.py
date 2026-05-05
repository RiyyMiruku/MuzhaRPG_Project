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
