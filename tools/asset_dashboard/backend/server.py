# tools/asset_dashboard/backend/server.py
"""FastAPI app for the asset dashboard.

Run: uv run uvicorn tools.asset_dashboard.backend.server:app --reload --port 8765
"""
from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Response
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .manifest_io import load_assets
from .thumbnails import resolve_thumbnail

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "art_source" / "manifest.json"

# Make `manifest` (the pipeline module) importable in this process for prompt edits.
sys.path.insert(0, str(REPO_ROOT / "pipeline"))
import manifest as pipeline_manifest  # noqa: E402
from .worker import worker_loop, pause as _worker_pause, resume as _worker_resume, is_paused as _worker_paused  # noqa: E402


@asynccontextmanager
async def _lifespan(app: FastAPI):
    # v2 worker runs alongside the legacy subprocess JobRegistry.
    # When v2 stages handle every asset path, the legacy path can retire.
    task = asyncio.create_task(worker_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="MuzhaRPG Asset Dashboard", version="0.2.0", lifespan=_lifespan)

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
    assets = [a.to_dict() for a in load_assets(pipeline_manifest.load())]
    return {"assets": assets, "manifest_path": str(MANIFEST_PATH)}


@app.get("/api/asset/{asset_type}/{name}/thumbnail")
def thumbnail(asset_type: str, name: str) -> FileResponse:
    if asset_type not in ("character", "tileset", "object"):
        raise HTTPException(400, "invalid asset_type")
    png = resolve_thumbnail(REPO_ROOT, asset_type, name, entry={})
    if png is None:
        raise HTTPException(404, "no thumbnail available")
    # See serve_asset_file for why no-cache + revalidation matters.
    return FileResponse(png, media_type="image/png", headers={"Cache-Control": "no-cache"})


class PromptUpdate(BaseModel):
    stage: str
    prompt: str


@app.patch("/api/asset/{asset_type}/{name}/prompts")
def update_prompt(asset_type: str, name: str, body: PromptUpdate) -> dict:
    if asset_type not in ("character", "tileset", "object"):
        raise HTTPException(400, "invalid asset_type")
    # Refuse to overwrite a prompt for an already-completed stage; client must POST /remake first.
    assets = {a.name: a for a in load_assets(pipeline_manifest.load()) if a.asset_type == asset_type}
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


def _delete_asset_files(asset_type: str, name: str) -> tuple[list[str], list[str]]:
    """Remove the on-disk files associated with an asset. Returns
    (deleted_paths, errors). Best-effort: a missing file is not an error,
    but a permission/IO failure is."""
    import shutil
    deleted: list[str] = []
    errors: list[str] = []

    # 1. Pipeline output directory under art_source/
    art_root = {
        "character": REPO_ROOT / "art_source" / "characters" / name,
        "tileset":   REPO_ROOT / "art_source" / "tilesets" / name,
        "object":    REPO_ROOT / "art_source" / "objects" / name,
    }[asset_type]
    if art_root.is_dir():
        try:
            shutil.rmtree(art_root)
            deleted.append(str(art_root.relative_to(REPO_ROOT)))
        except OSError as e:
            errors.append(f"{art_root}: {e}")

    # 2. Godot-imported files under game/. Include .import sidecars that
    # Godot's resource importer auto-generates.
    candidates: list[Path] = []
    if asset_type == "character":
        base = REPO_ROOT / "game" / "assets" / "textures" / "characters"
        for ext in (".png", ".json"):
            candidates.append(base / f"{name}{ext}")
            candidates.append(base / f"{name}{ext}.import")
    elif asset_type == "tileset":
        base = REPO_ROOT / "game" / "assets" / "textures" / "tilesets"
        candidates.append(base / f"{name}.png")
        candidates.append(base / f"{name}.png.import")
    elif asset_type == "object":
        tex_base = REPO_ROOT / "game" / "assets" / "textures" / "props"
        scn_base = REPO_ROOT / "game" / "src" / "maps" / "props"
        candidates.append(tex_base / f"{name}.png")
        candidates.append(tex_base / f"{name}.png.import")
        candidates.append(scn_base / f"{name}.tscn")
        candidates.append(scn_base / f"{name}.tscn.uid")  # Godot 4.x uid file

    for path in candidates:
        if path.is_file():
            try:
                path.unlink()
                deleted.append(str(path.relative_to(REPO_ROOT)))
            except OSError as e:
                errors.append(f"{path}: {e}")

    return deleted, errors


@app.delete("/api/asset/{asset_type}/{name}")
def delete_asset(asset_type: str, name: str, keep_files: bool = False) -> dict:
    """Remove an asset from the manifest AND delete its files on disk.
    Pass ?keep_files=true to preserve files (manifest-only delete)."""
    if asset_type not in ("character", "tileset", "object"):
        raise HTTPException(400, "invalid asset_type")
    remover = {
        "character": pipeline_manifest.remove_character,
        "tileset":   pipeline_manifest.remove_tileset,
        "object":    pipeline_manifest.remove_object,
    }[asset_type]
    if not remover(name):
        raise HTTPException(404, f"{asset_type} {name!r} not found")

    deleted_files: list[str] = []
    file_errors: list[str] = []
    if not keep_files:
        deleted_files, file_errors = _delete_asset_files(asset_type, name)

    return {
        "status": "ok",
        "deleted": name,
        "deleted_files": deleted_files,
        "file_errors": file_errors,
    }


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
    # Optional partial-direction filter for character animation stages.
    # When provided, orchestrator receives --only-directions and Pixellab is
    # asked to regen only those directions; compile_spritesheet patches only
    # the matching rows. Empty list == None == regen all.
    directions: list[str] | None = None


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
    # Optional per-stage prompt overrides for character animations. When set,
    # we pre-seed the manifest before the orchestrator starts so the first
    # run uses the custom action_description instead of the default "idle"/"walk".
    idle_action_description: str | None = None
    walk_action_description: str | None = None
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
    if asset_type == "character" and body.directions:
        cleaned = [d.strip() for d in body.directions if d and d.strip()]
        if cleaned:
            cmd += ["--only-directions", ",".join(cleaned)]
    # prop.py requires --kind even when resuming; pull it from the manifest entry.
    if asset_type == "object":
        raw = _read_manifest_raw()
        entry = (raw.get("objects") or {}).get(name) or {}
        kind = entry.get("kind")
        if kind:
            cmd += ["--kind", kind]
    # _ORCHESTRATOR_PATH points at npc_moving.py for all "character" assets, but
    # static NPCs use npc_static.py. Detect via manifest preset and swap script.
    if asset_type == "character":
        raw = _read_manifest_raw()
        entry = (raw.get("characters") or {}).get(name) or {}
        if entry.get("preset") == "npc":
            cmd[4] = "pipeline/orchestrators/npc_static.py"
            directions = entry.get("directions")
            if directions:
                cmd += ["--directions", str(directions)]
    job_id = _jobs.start(cmd, cwd=REPO_ROOT, asset_name=name, stage=body.stage)
    return {"job_id": job_id, "stage": body.stage}


# ============================================================
# v2 (file-per-asset + async stages, no subprocess)
# ============================================================


@app.get("/api/v2/worker/status")
def v2_worker_status() -> dict:
    return {"paused": _worker_paused()}


@app.post("/api/v2/worker/pause")
def v2_worker_pause() -> dict:
    """Stop dispatching new stages. In-flight tasks keep running until they
    finish or the backend stops. Asset reads/UI continue normally."""
    _worker_pause()
    return {"paused": True}


@app.post("/api/v2/worker/resume")
def v2_worker_resume() -> dict:
    _worker_resume()
    return {"paused": False}



#
# These endpoints skip subprocess+JobRegistry entirely and just write
# asset.json. The worker loop (started in lifespan) sees the new entry,
# resolves stage deps, and dispatches in-process async tasks under the
# pixellab_bg_job throttle.

class CreateCharacterV2(BaseModel):
    name: str
    description: str
    directions: int = 8                  # 4 (static NPC) or 8 (moving)
    view: str = "high_top_down"
    proportions: str = "cartoon"
    isometric: bool = False
    idle_template_id: str | None = None  # None → registry default (breathing-idle)
    walk_template_id: str | None = None  # None → registry default (walking-6-frames)
    zone: str | None = None
    category: str | None = None
    chapter: str | None = None
    preset: str = "player"               # 'player' (moving) | 'npc' (static)


@app.post("/api/v2/asset/character/{name}")
def v2_create_character(name: str, body: CreateCharacterV2) -> dict:
    """Create or upsert a character; the worker loop picks up and runs
    its stages asynchronously. Returns immediately with the asset's
    current state (status of each stage).

    Re-posting overwrites params + clears stage state so the worker
    re-runs from scratch. Use /api/v2/asset/character/{name}/stage/{stage}/retry
    to re-run a single stage instead.
    """
    if name != body.name:
        raise HTTPException(400, f"path name {name!r} != body name {body.name!r}")
    try:
        pipeline_manifest.validate_asset_name(name)
    except ValueError as e:
        raise HTTPException(400, f"invalid name: {e}") from e
    if body.directions not in (4, 8):
        raise HTTPException(400, "directions must be 4 or 8")

    fields = {
        "asset_type": "character",
        # Opt-in marker — without this the v2 worker leaves the asset alone.
        # Critical: legacy-pipeline assets share the manifest but use
        # different stage names; mixing them up overwrites real work.
        "pipeline_version": 2,
        "description": body.description,
        "directions": body.directions,
        "preset": body.preset,
        "params": {
            "view": body.view,
            "proportions": body.proportions,
            "isometric": body.isometric,
            "idle_template_id": body.idle_template_id,
            "walk_template_id": body.walk_template_id,
            "preset": body.preset,
        },
        # Clear stage state so worker re-runs from generate_rotations.
        "stages": {},
    }
    pipeline_manifest.upsert_character(name, fields)

    # Tags. Same vocabulary as legacy /create.
    tags = []
    if body.zone:     tags.append(f"zone:{body.zone}")
    if body.category: tags.append(f"category:{body.category}")
    if body.chapter:  tags.append(f"chapter:{body.chapter}")
    if tags:
        pipeline_manifest.add_tags("character", name, tags)

    entry = pipeline_manifest.get_character(name) or {}
    return {
        "status": "queued",
        "asset_type": "character",
        "name": name,
        "stages": entry.get("stages", {}),
    }


class V2RetryRequest(BaseModel):
    """Optional body. `directions` narrows partial regen for animation
    stages (animate_idle / animate_walk); ignored otherwise."""
    directions: list[str] | None = None


@app.post("/api/v2/asset/character/{name}/stage/{stage}/retry")
def v2_retry_stage(name: str, stage: str, body: V2RetryRequest | None = None) -> dict:
    """Reset a single stage so the worker re-runs it. If `directions` is
    given, the next run patches only those rows in the spritesheet (other
    directions keep their existing frames). Caller is responsible for ALSO
    resetting downstream stages if they want a cascade re-run."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "pipeline"))
    import stages as stages_mod
    if stages_mod.get_stage("character", stage) is None:
        raise HTTPException(404, f"unknown stage {stage!r}")
    entry = pipeline_manifest.get_character(name)
    if entry is None:
        raise HTTPException(404, f"character {name!r} not found")

    # Stash partial-direction request before resetting the stage so the
    # worker's next dispatch can read it. Only meaningful for animation
    # stages; non-animation stages just ignore it.
    if body and body.directions:
        retry_requests = dict(entry.get("retry_requests") or {})
        retry_requests[stage] = {"directions": list(body.directions)}
        pipeline_manifest.upsert_character(name, {"retry_requests": retry_requests})

    stages_mod.reset_stage("character", name, stage)
    return {
        "status": "reset", "name": name, "stage": stage,
        "directions": (list(body.directions) if body and body.directions else None),
    }


# ============================================================
# legacy (subprocess + JobRegistry) — still in use for object/tileset
# ============================================================


@app.post("/api/asset/create")
def create_asset(body: CreateAssetRequest) -> dict:
    # 1. validate name via pipeline_manifest.validate_asset_name
    try:
        pipeline_manifest.validate_asset_name(body.name)
    except ValueError as e:
        raise HTTPException(400, f"invalid name: {e}") from e

    # 2. refuse if asset already exists (caller should use /remake to redo)
    existing = {a.name: a for a in load_assets(pipeline_manifest.load()) if a.asset_type == body.asset_type}
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

    # 5. pre-seed manifest with custom animation prompts (character only).
    # The orchestrator's main() does `if not get_character(name): upsert(...)` so
    # this entry survives. run_character_animation reads the prompt for the
    # current stage via manifest.get_prompt — that's how this takes effect.
    if body.asset_type == "character" and (
        body.idle_action_description or body.walk_action_description
    ):
        pipeline_manifest.upsert_character(name=body.name, fields={"status": "init"})
        if body.idle_action_description:
            pipeline_manifest.set_prompt(
                "character", body.name, "add_idle_animation",
                body.idle_action_description,
            )
        if body.walk_action_description:
            pipeline_manifest.set_prompt(
                "character", body.name, "add_walk_animation",
                body.walk_action_description,
            )

    # 6. spawn subprocess
    cmd = ["uv", "run", "python", "-u", script] + cli_args
    job_id = _jobs.start(cmd, cwd=REPO_ROOT, asset_name=body.name, stage="create")
    return {"job_id": job_id, "asset_name": body.name, "asset_type": body.asset_type}


def _v2_active_stages_as_jobs() -> list[dict]:
    """Synthesize 'job' entries from v2 stages currently queued/running so
    they show up in dashboard /api/jobs alongside legacy subprocess jobs.
    Read straight from manifest each call — no separate registry to keep
    in sync with the actual on-disk state."""
    out: list[dict] = []
    data = pipeline_manifest.load()
    for bucket, asset_type in (("characters", "character"), ("tilesets", "tileset"), ("objects", "object")):
        for asset_name, entry in (data.get(bucket) or {}).items():
            if int(entry.get("pipeline_version", 1)) < 2:
                continue
            for stage_name, st in (entry.get("stages") or {}).items():
                status = st.get("status")
                if status not in ("queued", "running", "failed"):
                    continue
                out.append({
                    "id": f"v2:{asset_type}/{asset_name}/{stage_name}",
                    "asset_name": asset_name,
                    "stage": stage_name,
                    "status": status,
                    "exit_code": None,
                    "started_at": _ts_to_epoch(st.get("started_at") or st.get("queued_at")),
                    "finished_at": _ts_to_epoch(st.get("failed_at")) if status == "failed" else None,
                    "cmd": [],
                    "source": "v2",   # so frontend can badge differently if it wants
                })
    return out


def _ts_to_epoch(iso: str | None) -> float | None:
    if not iso:
        return None
    import datetime as _dt
    try:
        return _dt.datetime.fromisoformat(iso).timestamp()
    except ValueError:
        return None


@app.get("/api/jobs")
def list_jobs() -> dict:
    legacy = [j.to_dict() for j in _jobs.list()]
    for j in legacy:
        j.setdefault("source", "legacy")
    return {"jobs": legacy + _v2_active_stages_as_jobs()}


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
    """Aggregate manifest read. Returns the same shape as the legacy v1
    single manifest.json — `{characters, tilesets, objects}` — but in v2 it
    walks per-asset asset.json files via `pipeline_manifest.load()`. Kept as
    a shim because several call sites pluck raw stage paths or kind/preset
    fields from the bucket dict directly."""
    return pipeline_manifest.load()


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
    # Legacy stages stored output paths at stage_info["paths"]; v2 stages
    # store the same data inside stage_info["result"] under named keys.
    # Normalize so the rest of this handler doesn't care which format.
    raw_paths: list[str] = list(stage_info.get("paths") or [])
    result = stage_info.get("result") or {}
    if isinstance(result, dict):
        if isinstance(result.get("rotation_paths"), list):
            raw_paths.extend(result["rotation_paths"])
        for key in ("sheet_png", "sheet_json", "game_png", "game_json"):
            v = result.get(key)
            if isinstance(v, str):
                raw_paths.append(v)

    # Animation stages now save the whole spritesheet, not per-frame PNGs.
    # Expand into per-(action, direction) row crops so the dashboard can show
    # one thumbnail per direction. The crop endpoint slices on demand.
    images: list[dict] = []
    is_anim_stage = stage in (
        "add_idle_animation", "add_walk_animation",  # legacy
        "animate_idle", "animate_walk",              # v2
    )
    if asset_type == "character" and is_anim_stage:
        action_filter = "idle" if stage in ("add_idle_animation", "animate_idle") else "walk"
        sheet_path = next(
            (p for p in raw_paths if p.replace("\\", "/").endswith(".png")), None
        )
        json_path = next(
            (p for p in raw_paths if p.replace("\\", "/").endswith(".json")), None
        )
        if sheet_path and json_path:
            atlas_abs = (REPO_ROOT / json_path).resolve()
            try:
                atlas = _json.loads(atlas_abs.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                atlas = {}
            sheet_norm = sheet_path.replace("\\", "/")
            for key, anim in (atlas.get("animations") or {}).items():
                if not key.startswith(f"{action_filter}_"):
                    continue
                direction = key[len(action_filter) + 1:]
                row = anim.get("row")
                if not isinstance(row, int):
                    continue
                images.append({
                    "path": f"{sheet_norm}#{key}",
                    "url": (
                        f"/api/asset/sheet-row?p={urllib.parse.quote(sheet_norm, safe='')}"
                        f"&row={row}"
                    ),
                })
            # Always append the raw sheet+json links at the end for power use.
            for p in raw_paths:
                norm = p.replace("\\", "/")
                images.append({
                    "path": norm,
                    "url": f"/api/asset/file?p={urllib.parse.quote(norm, safe='')}",
                })

    if not images:
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


@app.get("/api/asset/sheet-row")
def sheet_row_crop(p: str, row: int) -> Response:
    """Return the Nth row of a character spritesheet as a standalone PNG.
    Row height comes from the sister `<name>.json`'s frame_size."""
    try:
        sheet_abs = (REPO_ROOT / p).resolve()
    except (OSError, ValueError):
        raise HTTPException(400, "invalid path")
    repo_root_abs = REPO_ROOT.resolve()
    allowed = False
    for r in _ALLOWED_FILE_ROOTS:
        try:
            sheet_abs.relative_to((repo_root_abs / r).resolve())
            allowed = True
            break
        except ValueError:
            continue
    if not allowed:
        raise HTTPException(403, "path outside allowed roots")
    if not sheet_abs.is_file() or sheet_abs.suffix.lower() != ".png":
        raise HTTPException(404, "sheet not found")
    json_path = sheet_abs.with_suffix(".json")
    fh = 92
    if json_path.is_file():
        try:
            atlas = _json.loads(json_path.read_text(encoding="utf-8"))
            fh = int((atlas.get("frame_size") or [92, 92])[1])
        except (OSError, ValueError):
            pass
    from PIL import Image
    import io
    with Image.open(sheet_abs) as img:
        w, h = img.size
        y0 = row * fh
        y1 = y0 + fh
        if y0 < 0 or y1 > h:
            raise HTTPException(416, f"row {row} out of bounds (sheet h={h}, fh={fh})")
        crop = img.crop((0, y0, w, y1))
        buf = io.BytesIO()
        crop.save(buf, "PNG", compress_level=6)
    return Response(content=buf.getvalue(), media_type="image/png")


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
    # Force browser to revalidate every time. FileResponse already sets ETag
    # + Last-Modified; the server returns 304 (cheap) when nothing changed.
    # Without `no-cache` browsers heuristic-cache PNGs by URL — re-rendering
    # an asset would show a stale sprite for minutes.
    return FileResponse(
        abs_path,
        media_type=mime or "application/octet-stream",
        headers={"Cache-Control": "no-cache"},
    )


from fastapi import Request  # noqa: E402


@app.put("/api/asset/file")
async def write_asset_file(p: str, request: Request) -> dict:
    """Atomic write of binary bytes to an existing path under allowed roots.

    Used by the dashboard's pixel editor: edit → encode PNG → PUT raw bytes.
    Refuses to create new files (path must already exist) — the editor
    only modifies existing assets, never creates new ones via this route.
    """
    try:
        abs_path = (REPO_ROOT / p).resolve()
    except (OSError, ValueError):
        raise HTTPException(400, "invalid path")
    repo_root_abs = REPO_ROOT.resolve()
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
        raise HTTPException(404, "file not found (PUT only overwrites existing)")
    # Refuse non-image extensions to keep blast radius narrow.
    if abs_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        raise HTTPException(400, f"refusing to overwrite non-image file: {abs_path.suffix}")

    body = await request.body()
    if not body:
        raise HTTPException(400, "empty body")
    if len(body) > 20 * 1024 * 1024:   # 20 MB cap; sprites are < 1 MB
        raise HTTPException(413, "body too large")

    # Atomic write: temp + rename, scoped to same directory so no cross-fs.
    import os as _os
    tmp = abs_path.with_suffix(abs_path.suffix + f".tmp.{_os.getpid()}")
    tmp.write_bytes(body)
    _os.replace(tmp, abs_path)
    return {"status": "ok", "path": p, "bytes_written": len(body)}


from fastapi.staticfiles import StaticFiles  # noqa: E402

_FRONTEND_DIST = REPO_ROOT / "tools" / "asset_dashboard" / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
