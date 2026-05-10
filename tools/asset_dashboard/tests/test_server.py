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
    monkeypatch.setattr(server.pipeline_manifest, "manifest_path", lambda: mpath)
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


def test_thumbnail_404_when_missing(client):
    r = client.get("/api/asset/character/alice/thumbnail")
    assert r.status_code == 404


def test_patch_prompt_for_unrealized_stage(client):
    r = client.patch(
        "/api/asset/character/alice/prompts",
        json={"stage": "add_walk_animation", "prompt": "limping"},
    )
    assert r.status_code == 200, r.text
    # GET back via manifest endpoint
    r2 = client.get("/api/manifest")
    alice = next(a for a in r2.json()["assets"] if a["name"] == "alice")
    assert alice["prompts"]["add_walk_animation"] == "limping"


def test_patch_prompt_for_completed_stage_blocked(client):
    r = client.patch(
        "/api/asset/character/alice/prompts",
        json={"stage": "generate_8dir_base", "prompt": "tries to overwrite"},
    )
    assert r.status_code == 409


def test_list_jobs_initially_empty(client):
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert r.json() == {"jobs": []}


def test_job_detail_404_for_missing(client):
    r = client.get("/api/jobs/nope")
    assert r.status_code == 404
