"""Tests for new client wrappers (HTTP mocked)."""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

import pixellab_client as plab


@patch("pixellab_client.requests.post")
def test_submit_character_4dir_calls_correct_url(mock_post: MagicMock) -> None:
    mock_post.return_value = MagicMock(
        status_code=200, json=lambda: {"character_id": "id-4dir"}
    )
    char_id = plab.submit_character_4dir(
        token="t", description="desc", size=64, view="high_top_down"
    )
    assert char_id == "id-4dir"
    args, kwargs = mock_post.call_args
    assert args[0] == plab.CREATE_CHAR_4DIR_URL
    assert kwargs["json"]["description"] == "desc"


@patch("pixellab_client.requests.post")
def test_submit_character_4dir_invalid_view_raises(mock_post: MagicMock) -> None:
    with pytest.raises(ValueError, match="view"):
        plab.submit_character_4dir(token="t", description="d", view="weird")


@patch("pixellab_client.requests.post")
def test_submit_character_4dir_no_id_raises(mock_post: MagicMock) -> None:
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {})
    with pytest.raises(RuntimeError, match="character_id"):
        plab.submit_character_4dir(token="t", description="d")


@patch("pixellab_client.requests.post")
def test_submit_iso_tile_returns_id(mock_post: MagicMock) -> None:
    mock_post.return_value = MagicMock(
        status_code=200, json=lambda: {"object_id": "iso-1"}
    )
    obj_id = plab.submit_iso_tile(token="t", description="lantern", size=32)
    assert obj_id == "iso-1"


def _make_b64_png() -> str:
    img = Image.new("RGBA", (4, 4), (255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_download_object_image_dict_base64(tmp_path: Path) -> None:
    out = tmp_path / "obj.png"
    meta: dict[str, Any] = {"image": {"base64": _make_b64_png()}}
    ok = plab.download_object_image(token="t", meta=meta, out_path=out)
    assert ok is True
    assert out.exists()
    assert out.stat().st_size > 0


@patch("pixellab_client.requests.get")
def test_download_object_image_url(mock_get: MagicMock, tmp_path: Path) -> None:
    out = tmp_path / "obj.png"
    mock_get.return_value = MagicMock(status_code=200, content=b"fakepngbytes")
    meta: dict[str, Any] = {"image_url": "https://example.com/foo.png"}
    ok = plab.download_object_image(token="tok", meta=meta, out_path=out)
    assert ok is True
    assert out.read_bytes() == b"fakepngbytes"
    args, kwargs = mock_get.call_args
    assert args[0] == "https://example.com/foo.png"
    assert kwargs["headers"]["Authorization"] == "Bearer tok"


def test_download_object_image_extra_keys_atlas(tmp_path: Path) -> None:
    out = tmp_path / "atlas.png"
    # Note: meta has neither 'image' nor 'image_url'; only 'atlas'.
    meta: dict[str, Any] = {"atlas": {"base64": _make_b64_png()}}
    ok = plab.download_object_image(
        token="t", meta=meta, out_path=out, extra_keys=("atlas",)
    )
    assert ok is True
    assert out.exists()
    assert out.stat().st_size > 0


def test_download_object_image_unparseable_writes_raw(tmp_path: Path) -> None:
    out = tmp_path / "sub" / "obj.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {"unexpected": "shape", "n": 1}
    ok = plab.download_object_image(token="t", meta=meta, out_path=out)
    assert ok is False
    raw = out.parent / "raw_response.json"
    assert raw.exists()
    parsed = json.loads(raw.read_text(encoding="utf-8"))
    assert parsed["unexpected"] == "shape"


def test_dead_v1_helpers_removed() -> None:
    assert not hasattr(plab, "call_pixflux"), "call_pixflux should be deleted"
    assert not hasattr(plab, "call_rotate"), "call_rotate should be deleted"
    assert not hasattr(plab, "call_animate_with_text_v3"), \
        "call_animate_with_text_v3 should be deleted"
    assert not hasattr(plab, "PIXFLUX_URL")
    assert not hasattr(plab, "ROTATE_URL")
    assert not hasattr(plab, "ANIMATE_TEXT_V3_URL")
