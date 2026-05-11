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
MANIFEST_PATH = REPO_ROOT / "art_source" / "pipeline" / "output" / "manifest.json"

# Make `manifest` (the pipeline module) importable in this process for prompt edits.
sys.path.insert(0, str(REPO_ROOT / "art_source" / "pipeline"))
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


from .jobs import JobRegistry, JobStatus  # noqa: E402

_jobs = JobRegistry()


_ORCHESTRATOR_PATH: dict[str, str] = {
    "character": "art_source/pipeline/orchestrators/npc_moving.py",
    "tileset": "art_source/pipeline/orchestrators/autotile.py",
    "object": "art_source/pipeline/orchestrators/prop.py",
}


class RemakeRequest(BaseModel):
    stage: str
    prompt: str | None = None


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


import urllib.parse
import json as _json
import mimetypes


_ALLOWED_FILE_ROOTS: list[str] = [
    "art_source/pipeline/output",
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
