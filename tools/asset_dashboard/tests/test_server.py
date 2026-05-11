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


def test_stage_returns_images_and_prompt(client, tmp_path, monkeypatch):
    """The /stage endpoint reports stage completion + paths + prompt."""
    # Seed the manifest with a completed stage that has paths.
    mpath = tmp_path / "manifest.json"
    mpath.write_text(json.dumps({
        "version": 1,
        "characters": {
            "alice": {
                "description": "alice base prompt",
                "tags": ["zone:nccu"],
                "stages": {
                    "generate_8dir_base": {
                        "completed_at": "2026-01-01T00:00:00",
                        "paths": [
                            "art_source\\pipeline\\output\\characters\\alice\\rotations\\south.png",
                            "art_source\\pipeline\\output\\characters\\alice\\rotations\\east.png",
                        ],
                    },
                },
                "prompts": {"add_idle_animation": "casting calmly"},
            }
        },
        "tilesets": {}, "objects": {},
    }), encoding="utf-8")
    monkeypatch.setattr(server, "MANIFEST_PATH", mpath)
    monkeypatch.setattr(server.pipeline_manifest, "manifest_path", lambda: mpath)

    r = client.get("/api/asset/character/alice/stage/generate_8dir_base")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["stage"] == "generate_8dir_base"
    assert data["completed_at"] == "2026-01-01T00:00:00"
    # generate_*_base falls back to description when no explicit prompt is stored.
    assert data["prompt"] == "alice base prompt"
    assert len(data["images"]) == 2
    # Paths normalized to forward slashes.
    assert data["images"][0]["path"] == "art_source/pipeline/output/characters/alice/rotations/south.png"
    # URL points at the file-serving endpoint with encoded p.
    assert data["images"][0]["url"].startswith("/api/asset/file?p=")
    assert "south.png" in data["images"][0]["url"]


def test_stage_not_yet_completed_returns_empty(client):
    r = client.get("/api/asset/character/alice/stage/add_walk_animation")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["completed_at"] is None
    assert data["images"] == []


def test_stage_unknown_asset_404(client):
    r = client.get("/api/asset/character/nobody/stage/generate_8dir_base")
    assert r.status_code == 404


def test_stage_invalid_asset_type_400(client):
    r = client.get("/api/asset/widget/alice/stage/whatever")
    assert r.status_code == 400


def test_file_serves_existing_png(client, tmp_path, monkeypatch):
    # Place a PNG inside the allowed area
    fake_png = tmp_path / "art_source/pipeline/output/characters/alice/rotations/south.png"
    fake_png.parent.mkdir(parents=True)
    fake_png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    r = client.get("/api/asset/file", params={"p": "art_source/pipeline/output/characters/alice/rotations/south.png"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("image/")
    assert r.content.startswith(b"\x89PNG")


def test_file_rejects_path_outside_allowed_roots(client, tmp_path, monkeypatch):
    outside = tmp_path / "secret.txt"
    outside.write_text("nope")
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    r = client.get("/api/asset/file", params={"p": "secret.txt"})
    assert r.status_code == 403


def test_file_rejects_path_traversal(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    r = client.get("/api/asset/file", params={"p": "art_source/pipeline/output/../../../etc/passwd"})
    assert r.status_code in (400, 403, 404)


def test_file_missing_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    (tmp_path / "art_source/pipeline/output").mkdir(parents=True)
    r = client.get("/api/asset/file", params={"p": "art_source/pipeline/output/ghost.png"})
    assert r.status_code == 404
