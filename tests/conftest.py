"""Shared pytest fixtures."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import pytest


@pytest.fixture
def isolated_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect manifest.json to tmp_path so tests don't touch real output/."""
    import manifest as m

    fake = tmp_path / "manifest.json"
    monkeypatch.setattr(m, "manifest_path", lambda: fake)
    monkeypatch.setattr(m, "output_dir", lambda: tmp_path)
    yield fake
