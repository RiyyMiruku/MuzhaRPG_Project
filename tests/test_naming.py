"""Tests for asset naming convention + tag-based query."""
from __future__ import annotations

from pathlib import Path

import pytest

import manifest


# === validate_asset_name ===


@pytest.mark.parametrize(
    "name",
    [
        "chen_ayi",
        "vendor_market_01",
        "red_lantern",
        "market_grass_asphalt",
        "a3c",  # min length
    ],
)
def test_validate_asset_name_accepts_valid(name: str) -> None:
    manifest.validate_asset_name(name)  # should not raise


@pytest.mark.parametrize(
    "name",
    [
        "Chen_ayi",       # uppercase
        "_leading",       # underscore start
        "trailing_",      # underscore end
        "double__under",  # double underscore
        "ab",             # too short
        "a" * 70,         # too long
        "with-dash",      # hyphen
        "with space",     # space
        "123start",       # digit start
        "中文名",         # non-ASCII
    ],
)
def test_validate_asset_name_rejects_invalid(name: str) -> None:
    with pytest.raises(ValueError):
        manifest.validate_asset_name(name)


def test_validate_asset_name_non_string_raises() -> None:
    with pytest.raises(ValueError):
        manifest.validate_asset_name(123)  # type: ignore[arg-type]


# === add_tags ===


def test_add_tags_adds_dedupes_and_preserves_order(isolated_manifest: Path) -> None:
    manifest.upsert_character("alice", {"character_id": "u1"})
    manifest.add_tags("character", "alice", ["zone:market", "category:vendor"])
    manifest.add_tags("character", "alice", ["zone:market", "extra"])  # dedupe
    char = manifest.get_character("alice")
    assert char is not None
    assert char["tags"] == ["zone:market", "category:vendor", "extra"]


def test_add_tags_unknown_name_raises(isolated_manifest: Path) -> None:
    with pytest.raises(KeyError, match="not found"):
        manifest.add_tags("character", "ghost", ["x"])


def test_add_tags_unknown_asset_type_raises(isolated_manifest: Path) -> None:
    with pytest.raises(ValueError, match="unknown asset_type"):
        manifest.add_tags("widget", "x", ["t"])


# === query_assets ===


def _seed(_isolated: Path) -> None:
    manifest.upsert_character("alice", {"character_id": "u1"})
    manifest.add_tags("character", "alice", ["zone:market", "category:vendor"])
    manifest.upsert_character("bob", {"character_id": "u2"})
    manifest.add_tags("character", "bob", ["zone:nccu", "category:student"])
    manifest.upsert_tileset("market_grass_asphalt", {"tileset_id": "t1"})
    manifest.add_tags("tileset", "market_grass_asphalt", ["zone:market"])
    manifest.upsert_object("red_lantern", {"object_id": "o1"})
    manifest.add_tags("object", "red_lantern", ["zone:market", "category:decoration"])


def test_query_assets_no_filter_returns_all(isolated_manifest: Path) -> None:
    _seed(isolated_manifest)
    results = manifest.query_assets()
    assert set(results.keys()) == {
        "character:alice",
        "character:bob",
        "tileset:market_grass_asphalt",
        "object:red_lantern",
    }


def test_query_assets_filter_by_asset_type(isolated_manifest: Path) -> None:
    _seed(isolated_manifest)
    results = manifest.query_assets(asset_type="character")
    assert set(results.keys()) == {"character:alice", "character:bob"}


def test_query_assets_filter_by_tags_and_logic(isolated_manifest: Path) -> None:
    _seed(isolated_manifest)
    # Both tags must be present
    r = manifest.query_assets(tags=["zone:market", "category:vendor"])
    assert set(r.keys()) == {"character:alice"}
    # Only zone:market — multiple matches across types
    r = manifest.query_assets(tags=["zone:market"])
    assert set(r.keys()) == {
        "character:alice",
        "tileset:market_grass_asphalt",
        "object:red_lantern",
    }


def test_query_assets_returns_typed_keys(isolated_manifest: Path) -> None:
    _seed(isolated_manifest)
    results = manifest.query_assets(asset_type="object")
    assert "object:red_lantern" in results
    # values are entry dicts
    assert results["object:red_lantern"]["object_id"] == "o1"


def test_query_assets_unknown_asset_type_raises(isolated_manifest: Path) -> None:
    with pytest.raises(ValueError, match="unknown asset_type"):
        manifest.query_assets(asset_type="widget")
