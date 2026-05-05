"""Tests for new client wrappers (HTTP mocked)."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

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


def test_dead_v1_helpers_removed() -> None:
    assert not hasattr(plab, "call_pixflux"), "call_pixflux should be deleted"
    assert not hasattr(plab, "call_rotate"), "call_rotate should be deleted"
    assert not hasattr(plab, "call_animate_with_text_v3"), \
        "call_animate_with_text_v3 should be deleted"
    assert not hasattr(plab, "PIXFLUX_URL")
    assert not hasattr(plab, "ROTATE_URL")
    assert not hasattr(plab, "ANIMATE_TEXT_V3_URL")
