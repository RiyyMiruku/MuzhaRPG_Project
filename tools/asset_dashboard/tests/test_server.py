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
                            "pipeline\\output\\characters\\alice\\rotations\\south.png",
                            "pipeline\\output\\characters\\alice\\rotations\\east.png",
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
    assert data["images"][0]["path"] == "pipeline/output/characters/alice/rotations/south.png"
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
    fake_png = tmp_path / "pipeline/output/characters/alice/rotations/south.png"
    fake_png.parent.mkdir(parents=True)
    fake_png.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    r = client.get("/api/asset/file", params={"p": "pipeline/output/characters/alice/rotations/south.png"})
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
    r = client.get("/api/asset/file", params={"p": "pipeline/output/../../../etc/passwd"})
    assert r.status_code in (400, 403, 404)


def test_file_missing_404(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "REPO_ROOT", tmp_path)
    (tmp_path / "pipeline/output").mkdir(parents=True)
    r = client.get("/api/asset/file", params={"p": "pipeline/output/ghost.png"})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/asset/create tests
# ---------------------------------------------------------------------------

@pytest.fixture
def stub_jobs(monkeypatch):
    """Replace JobRegistry.start with a stub that records calls but does NOT spawn subprocesses."""
    from tools.asset_dashboard.backend import server as srv_mod
    calls = []

    def fake_start(cmd, cwd=None, asset_name=None, stage=None):
        calls.append({"cmd": cmd, "cwd": cwd, "asset_name": asset_name, "stage": stage})
        # Insert a synthetic JobInfo so list_jobs() still returns it
        from tools.asset_dashboard.backend.jobs import JobInfo, JobStatus
        import uuid, time, tempfile
        from pathlib import Path
        jid = uuid.uuid4().hex[:12]
        log = Path(tempfile.gettempdir()) / f"stub_{jid}.log"
        log.write_text("", encoding="utf-8")
        info = JobInfo(
            id=jid, cmd=list(cmd), cwd=Path(cwd or "."), log_path=log,
            status=JobStatus.RUNNING, asset_name=asset_name, stage=stage,
        )
        srv_mod._jobs._jobs[jid] = info
        return jid

    monkeypatch.setattr(srv_mod._jobs, "start", fake_start)
    return calls


def test_create_character_moving_spawns_job(client, stub_jobs):
    r = client.post(
        "/api/asset/create",
        json={
            "asset_type": "character",
            "kind": "moving",
            "name": "newbie_npc",
            "description": "a brave new character",
            "zone": "market",
            "category": "vendor",
            "chapter": "1",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["asset_name"] == "newbie_npc"
    assert data["asset_type"] == "character"
    assert "job_id" in data

    # job appears in /api/jobs
    jobs = client.get("/api/jobs").json()["jobs"]
    assert any(j["asset_name"] == "newbie_npc" for j in jobs)


def test_create_existing_asset_rejected(client):
    # The fixture seeds 'alice' as a character
    r = client.post(
        "/api/asset/create",
        json={
            "asset_type": "character",
            "kind": "moving",
            "name": "alice",
            "description": "would clash",
        },
    )
    assert r.status_code == 409


def test_create_invalid_name_rejected(client):
    r = client.post(
        "/api/asset/create",
        json={
            "asset_type": "character",
            "kind": "moving",
            "name": "Bad Name With Spaces",
            "description": "x",
        },
    )
    assert r.status_code == 400


def test_create_character_requires_kind(client):
    r = client.post(
        "/api/asset/create",
        json={
            "asset_type": "character",
            "name": "no_kind",
            "description": "x",
        },
    )
    assert r.status_code == 400


def test_create_object_iso_prop(client, stub_jobs):
    r = client.post(
        "/api/asset/create",
        json={
            "asset_type": "object",
            "kind": "iso_prop",
            "name": "test_lantern",
            "description": "red lantern",
            "size": 32,
            "collision": "none",
        },
    )
    assert r.status_code == 200, r.text


def test_create_tileset(client, stub_jobs):
    r = client.post(
        "/api/asset/create",
        json={
            "asset_type": "tileset",
            "name": "test_grass_dirt",
            "lower": "grass",
            "upper": "dirt",
            "transition_size": 0.2,
        },
    )
    assert r.status_code == 200, r.text


def test_create_tileset_missing_lower_upper(client):
    r = client.post(
        "/api/asset/create",
        json={
            "asset_type": "tileset",
            "name": "incomplete_tileset",
        },
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/asset/{type}/{name} tests
# ---------------------------------------------------------------------------

def test_delete_asset_removes_from_manifest(client, tmp_path, monkeypatch):
    # alice is seeded by the client fixture
    r = client.delete("/api/asset/character/alice")
    assert r.status_code == 200, r.text
    assert r.json()["deleted"] == "alice"

    # confirm gone from /api/manifest
    listing = client.get("/api/manifest").json()
    assert not any(a["name"] == "alice" for a in listing["assets"])


def test_delete_asset_404_for_missing(client):
    r = client.delete("/api/asset/character/nobody")
    assert r.status_code == 404


def test_delete_asset_invalid_type(client):
    r = client.delete("/api/asset/widget/alice")
    assert r.status_code == 400
