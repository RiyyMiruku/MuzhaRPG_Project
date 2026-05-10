# tools/asset_dashboard/tests/test_server.py
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tools.asset_dashboard.backend import server


@pytest.fixture
def client(tmp_path, monkeypatch):
    mpath = tmp_path / "manifest.json"
    mpath.write_text(json.dumps({
        "version": 1,
        "characters": {
            "alice": {
                "description": "alice",
                "tags": ["zone:nccu", "chapter:1"],
                "stages": {"generate_8dir_base": {"completed_at": "2026-01-01"}},
                "prompts": {},
            }
        },
        "tilesets": {}, "objects": {},
    }), encoding="utf-8")
    monkeypatch.setattr(server, "MANIFEST_PATH", mpath)
    return TestClient(server.app)


def test_get_manifest_returns_assets(client):
    r = client.get("/api/manifest")
    assert r.status_code == 200
    data = r.json()
    assert "assets" in data
    names = [a["name"] for a in data["assets"]]
    assert "alice" in names


def test_get_manifest_includes_progress(client):
    r = client.get("/api/manifest")
    alice = next(a for a in r.json()["assets"] if a["name"] == "alice")
    assert alice["progress"] == "1/5"
    assert alice["chapter"] == "1"


def test_health_endpoint(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
