# tools/asset_dashboard/backend/server.py
"""FastAPI app for the asset dashboard.

Run: uv run uvicorn tools.asset_dashboard.backend.server:app --reload --port 8765
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .manifest_io import load_assets
from .thumbnails import resolve_thumbnail

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "art_source" / "manifest.json"

# Make `manifest` (the pipeline module) importable in this process for prompt edits.
sys.path.insert(0, str(REPO_ROOT / "pipeline"))
import manifest as pipeline_manifest  # noqa: E402

app = FastAPI(title="MuzhaRPG Asset Dashboard", version="0.1.0")

# Vite dev server runs on 5173 by default; allow it to call the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/manifest")
def manifest() -> dict:
    assets = [a.to_dict() for a in load_assets(MANIFEST_PATH)]
    return {"assets": assets, "manifest_path": str(MANIFEST_PATH)}


@app.get("/api/asset/{asset_type}/{name}/thumbnail")
def thumbnail(asset_type: str, name: str) -> FileResponse:
    if asset_type not in ("character", "tileset", "object"):
        raise HTTPException(400, "invalid asset_type")
    png = resolve_thumbnail(REPO_ROOT, asset_type, name, entry={})
    if png is None:
        raise HTTPException(404, "no thumbnail available")
    return FileResponse(png, media_type="image/png")


class PromptUpdate(BaseModel):
    stage: str
    prompt: str


@app.patch("/api/asset/{asset_type}/{name}/prompts")
def update_prompt(asset_type: str, name: str, body: PromptUpdate) -> dict:
    if asset_type not in ("character", "tileset", "object"):
        raise HTTPException(400, "invalid asset_type")
    # Refuse to overwrite a prompt for an already-completed stage; client must POST /remake first.
    assets = {a.name: a for a in load_assets(MANIFEST_PATH) if a.asset_type == asset_type}
    asset = assets.get(name)
    if asset is None:
        raise HTTPException(404, f"{asset_type} {name!r} not found")
    if body.stage in asset.completed_stages:
        raise HTTPException(
            409,
            f"stage {body.stage!r} already completed; call POST /api/asset/.../remake to unlock",
        )
    try:
        pipeline_manifest.set_prompt(asset_type, name, body.stage, body.prompt)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    return {"status": "ok", "stage": body.stage, "prompt": body.prompt}


@app.delete("/api/asset/{asset_type}/{name}")
def delete_asset(asset_type: str, name: str) -> dict:
    """Remove an asset from the manifest. Does NOT delete files on disk."""
    if asset_type not in ("character", "tileset", "object"):
        raise HTTPException(400, "invalid asset_type")
    bucket = {"character": "characters", "tileset": "tilesets", "object": "objects"}[asset_type]
    import json as _json_del
    if not MANIFEST_PATH.exists():
        raise HTTPException(404, "manifest missing")
    data = _json_del.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if name not in (data.get(bucket) or {}):
        raise HTTPException(404, f"{asset_type} {name!r} not found")
    del data[bucket][name]
    MANIFEST_PATH.write_text(_json_del.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"status": "ok", "deleted": name}


from .jobs import JobRegistry, JobStatus  # noqa: E402

_jobs = JobRegistry()


_ORCHESTRATOR_PATH: dict[str, str] = {
    "character": "pipeline/orchestrators/npc_moving.py",
    "tileset": "pipeline/orchestrators/autotile.py",
    "object": "pipeline/orchestrators/prop.py",
}


class RemakeRequest(BaseModel):
    stage: str
    prompt: str | None = None


class CreateAssetRequest(BaseModel):
    asset_type: str           # "character" | "tileset" | "object"
    kind: str | None = None   # character: "moving"|"static"; object: "iso_prop"|"building"
    name: str
    description: str | None = None
    zone: str | None = None
    category: str | None = None
    chapter: str | None = None
    # character
    directions: int | None = None         # static only (4 or 8)
    view: str | None = None
    proportions: str | None = None
    idle_frame_count: int | None = None
    walk_frame_count: int | None = None
    no_idle: bool | None = None           # static only
    # object
    size: int | None = None               # iso_prop
    width: int | None = None              # building
    height: int | None = None             # building
    collision: str | None = None
    has_collision: bool | None = None
    # tileset
    lower: str | None = None
    upper: str | None = None
    transition_size: float | None = None
    transition_description: str | None = None


@app.post("/api/asset/{asset_type}/{name}/remake")
def remake(asset_type: str, name: str, body: RemakeRequest) -> dict:
    if asset_type not in _ORCHESTRATOR_PATH:
        raise HTTPException(400, "invalid asset_type")
    # Optionally update the prompt first.
    if body.prompt is not None:
        try:
            pipeline_manifest.set_prompt(asset_type, name, body.stage, body.prompt)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e

    cmd: list[str] = [
        "uv", "run", "python", "-u",
        _ORCHESTRATOR_PATH[asset_type],
        "--name", name,
        "--review-mode", "none",
        "--force-restart-stage", body.stage,
        "--resume-from", body.stage,
    ]
    job_id = _jobs.start(cmd, cwd=REPO_ROOT, asset_name=name, stage=body.stage)
    return {"job_id": job_id, "stage": body.stage}


@app.post("/api/asset/create")
def create_asset(body: CreateAssetRequest) -> dict:
    # 1. validate name via pipeline_manifest.validate_asset_name
    try:
        pipeline_manifest.validate_asset_name(body.name)
    except ValueError as e:
        raise HTTPException(400, f"invalid name: {e}") from e

    # 2. refuse if asset already exists (caller should use /remake to redo)
    existing = {a.name: a for a in load_assets(MANIFEST_PATH) if a.asset_type == body.asset_type}
    if body.name in existing:
        raise HTTPException(409, f"{body.asset_type} {body.name!r} already exists; use /remake instead")

    # 3. build CLI command based on asset_type + kind
    script: str
    cli_args: list[str] = ["--name", body.name, "--review-mode", "none"]

    if body.asset_type == "character":
        if body.kind == "static":
            script = "pipeline/orchestrators/npc_static.py"
            if body.directions is not None:
                cli_args += ["--directions", str(body.directions)]
            if body.no_idle:
                cli_args += ["--no-idle"]
            if body.idle_frame_count is not None:
                cli_args += ["--idle-frame-count", str(body.idle_frame_count)]
        elif body.kind == "moving":
            script = "pipeline/orchestrators/npc_moving.py"
            if body.idle_frame_count is not None:
                cli_args += ["--idle-frame-count", str(body.idle_frame_count)]
            if body.walk_frame_count is not None:
                cli_args += ["--walk-frame-count", str(body.walk_frame_count)]
        else:
            raise HTTPException(400, "character kind must be 'moving' or 'static'")
        if not body.description:
            raise HTTPException(400, "character requires description")
        cli_args += ["--description", body.description]
        if body.view:
            cli_args += ["--view", body.view]
        if body.proportions:
            cli_args += ["--proportions", body.proportions]

    elif body.asset_type == "object":
        if body.kind not in ("iso_prop", "building"):
            raise HTTPException(400, "object kind must be 'iso_prop' or 'building'")
        script = "pipeline/orchestrators/prop.py"
        if not body.description:
            raise HTTPException(400, "object requires description")
        cli_args += ["--kind", body.kind, "--description", body.description]
        if body.kind == "iso_prop" and body.size is not None:
            cli_args += ["--size", str(body.size)]
        if body.kind == "building":
            if body.width is not None:
                cli_args += ["--width", str(body.width)]
            if body.height is not None:
                cli_args += ["--height", str(body.height)]
            if body.view:
                cli_args += ["--view", body.view]
        if body.collision:
            cli_args += ["--collision", body.collision]
        if body.has_collision is False:
            cli_args += ["--no-collision"]

    elif body.asset_type == "tileset":
        script = "pipeline/orchestrators/autotile.py"
        if not body.lower or not body.upper:
            raise HTTPException(400, "tileset requires lower and upper")
        cli_args += ["--lower", body.lower, "--upper", body.upper]
        if body.transition_size is not None:
            cli_args += ["--transition-size", str(body.transition_size)]
        if body.transition_description:
            cli_args += ["--transition-description", body.transition_description]

    else:
        raise HTTPException(400, "asset_type must be character | tileset | object")

    # 4. zone / category / chapter (now supported by orchestrators after Part A)
    if body.zone:
        cli_args += ["--zone", body.zone]
    if body.category:
        cli_args += ["--category", body.category]
    if body.chapter:
        cli_args += ["--chapter", body.chapter]

    # 5. spawn subprocess
    cmd = ["uv", "run", "python", "-u", script] + cli_args
    job_id = _jobs.start(cmd, cwd=REPO_ROOT, asset_name=body.name, stage="create")
    return {"job_id": job_id, "asset_name": body.name, "asset_type": body.asset_type}


@app.get("/api/jobs")
def list_jobs() -> dict:
    return {"jobs": [j.to_dict() for j in _jobs.list()]}


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str) -> dict:
    info = _jobs.get(job_id)
    if info is None:
        raise HTTPException(404, "job not found")
    d = info.to_dict()
    d["tail"] = info.tail(n=200)
    return d


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    """Remove a finished (completed/failed) job from the registry."""
    info = _jobs.get(job_id)
    if info is None:
        raise HTTPException(404, "job not found")
    if not _jobs.remove(job_id):
        raise HTTPException(409, f"refused: job is {info.status.value} (only finished jobs can be removed)")
    return {"status": "ok", "removed": job_id}


@app.delete("/api/jobs")
def clear_finished_jobs() -> dict:
    """Remove ALL completed + failed jobs at once. Running jobs stay."""
    count = _jobs.clear_finished()
    return {"status": "ok", "removed_count": count}


import urllib.parse
import json as _json
import mimetypes


_ALLOWED_FILE_ROOTS: list[str] = [
    "art_source",
    "game/assets/textures",
]


def _read_manifest_raw() -> dict:
    """Direct JSON read of the manifest file. Used by stage_detail to access
    raw stages structure (load_assets() doesn't expose stage.paths)."""
    if not MANIFEST_PATH.exists():
        return {}
    return _json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@app.get("/api/asset/{asset_type}/{name}/stage/{stage}")
def stage_detail(asset_type: str, name: str, stage: str) -> dict:
    if asset_type not in ("character", "tileset", "object"):
        raise HTTPException(400, "invalid asset_type")

    # Find the asset entry in the manifest.
    data = _read_manifest_raw()
    bucket = {"character": "characters", "tileset": "tilesets", "object": "objects"}[asset_type]
    asset = (data.get(bucket) or {}).get(name)
    if asset is None:
        raise HTTPException(404, f"{asset_type} {name!r} not found")

    stages = asset.get("stages") or {}
    stage_info = stages.get(stage) or {}
    raw_paths: list[str] = list(stage_info.get("paths") or [])
    images: list[dict] = []
    for p in raw_paths:
        norm = p.replace("\\", "/")
        images.append({
            "path": norm,
            "url": f"/api/asset/file?p={urllib.parse.quote(norm, safe='')}",
        })

    prompt = pipeline_manifest.get_prompt(asset_type, name, stage)
    return {
        "stage": stage,
        "completed_at": stage_info.get("completed_at"),
        "prompt": prompt,
        "images": images,
    }


@app.get("/api/asset/file")
def serve_asset_file(p: str) -> FileResponse:
    # Resolve to absolute path under REPO_ROOT and verify containment.
    try:
        abs_path = (REPO_ROOT / p).resolve()
    except (OSError, ValueError):
        raise HTTPException(400, "invalid path")
    repo_root_abs = REPO_ROOT.resolve()
    # Check that the resolved path is under one of the allowed roots.
    allowed = False
    for root in _ALLOWED_FILE_ROOTS:
        root_abs = (repo_root_abs / root).resolve()
        try:
            abs_path.relative_to(root_abs)
            allowed = True
            break
        except ValueError:
            continue
    if not allowed:
        raise HTTPException(403, "path outside allowed roots")
    if not abs_path.is_file():
        raise HTTPException(404, "file not found")
    mime, _ = mimetypes.guess_type(str(abs_path))
    return FileResponse(abs_path, media_type=mime or "application/octet-stream")


from fastapi.staticfiles import StaticFiles  # noqa: E402

_FRONTEND_DIST = REPO_ROOT / "tools" / "asset_dashboard" / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
