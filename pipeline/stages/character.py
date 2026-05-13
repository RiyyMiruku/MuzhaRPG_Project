"""Character pipeline as async stages.

Each function runs inside the dashboard backend's event loop — no
subprocess. The runner (in stages/__init__.py + backend worker loop)
respects throttle, dependency order, and per-stage state machine.

Pipeline (inferred from asset.directions and asset.params):
  generate_rotations  → animate_idle ─┐
                       ╲              ├→ import_to_godot
                        animate_walk ─┘   (walk only if directions==8)

Static NPCs (directions=4) skip animate_walk; animate_idle still runs and
import_to_godot's deps are satisfied with just idle.
"""
from __future__ import annotations

import asyncio
import io
import sys
from pathlib import Path
from typing import Any

# pipeline/ is on sys.path (dashboard server adds it; CLI script also)
import animation_templates as at
import manifest
import pixellab_async as plab
import pixellab_client as plab_sync  # for non-HTTP helpers (load_token, project_root, _decode_image_entry)
import post_process as pp
import spritesheet

from . import StageContext, stage


# === Internal helpers ===


def _save_rotations(images: dict, char_dir: Path) -> dict[str, Path]:
    """Chroma-key each rotation PNG and write to char_dir/rotations/<dir>.png."""
    out_dir = char_dir / "rotations"
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: dict[str, Path] = {}
    for direction, img in images.items():
        img = pp.chroma_key_bg(img)
        fname = direction.replace("-", "_") + ".png"
        out = out_dir / fname
        img.save(out)
        saved[direction] = out
    return saved


async def _poll_one_direction(
    token: str, direction: str, job_id: str
) -> tuple[str, list]:
    """Poll one Pixellab background job, decode its frames. Returns (direction, [PIL frames])."""
    result = await plab.poll_background_job(token, job_id)
    items = result.get("images") or []
    frames: list = []
    for i, item in enumerate(items):
        img = plab_sync._decode_image_entry(item)
        if img is None:
            raise RuntimeError(
                f"animation frame {direction}/{i} failed to decode "
                f"(item type={type(item).__name__})"
            )
        frames.append(pp.chroma_key_bg(img))
    return direction, frames


async def _run_animation(
    ctx: StageContext,
    *,
    action: str,                # "idle" | "walk"
    template_id: str,
    directions: list[str],
) -> dict[str, Any]:
    """Submit + poll an animation; write frames to char's spritesheet.

    Common body for animate_idle / animate_walk. Polls all direction jobs
    in parallel via asyncio.gather (Pixellab's quota throttles upstream).

    Honors partial-direction retry: if asset.retry_requests[stage_name]
    is set (the v2 retry endpoint stashes it when given a `directions`
    body), narrow this run to that subset and clear the request after
    success. Other directions keep their existing spritesheet rows.
    """
    char = ctx.asset
    char_id = char.get("character_id")
    if not char_id:
        raise RuntimeError(
            f"character {ctx.name} has no character_id — generate_rotations "
            f"must complete before animation stages"
        )
    token = plab_sync.load_token()

    stage_name = f"animate_{action}"
    retry_req = (char.get("retry_requests") or {}).get(stage_name) or {}
    requested = retry_req.get("directions")
    if requested:
        wanted = set(requested)
        directions = [d for d in directions if d in wanted]
        if not directions:
            return {
                "skipped": True,
                "reason": f"retry_requests.{stage_name}.directions {sorted(wanted)} "
                          f"has no overlap with template defaults",
            }
        print(f"[partial] {stage_name} only: {directions}", flush=True)

    submitted = await plab.submit_character_animation(
        token=token,
        character_id=char_id,
        directions=directions,
        template_animation_id=template_id,
        isometric=ctx.params.get("isometric", False),
    )

    # Poll every direction concurrently. Pixellab background jobs themselves
    # are limited by Pixellab's internal pool; our asyncio.gather just lets
    # us not stall on one slow direction.
    polled = await asyncio.gather(*[
        _poll_one_direction(token, d, jid)
        for d, jid in zip(submitted["directions"], submitted["background_job_ids"])
    ])

    # Write frames into char's spritesheet under a single sheet write.
    char_dir = manifest.character_dir(ctx.name)
    sheet, atlas = spritesheet.load_or_init_sheet(char_dir)
    for direction, frames in polled:
        sheet, atlas = spritesheet.write_animation_frames(
            sheet, atlas, action, direction, frames
        )
    sheet_png, sheet_json = spritesheet.save_sheet(char_dir, sheet, atlas)

    # Update char animations index.
    animations = char.get("animations", {})
    animations.setdefault(action, [])
    for d in submitted["directions"]:
        if d not in animations[action]:
            animations[action].append(d)
    fields_to_save: dict[str, Any] = {"animations": animations}

    # Clear the retry_requests slot we honored so the next ordinary run
    # doesn't re-narrow to the same partial set.
    if requested:
        cleared = dict(char.get("retry_requests") or {})
        cleared.pop(stage_name, None)
        fields_to_save["retry_requests"] = cleared
    manifest.upsert_character(ctx.name, fields_to_save)

    rel_root = plab_sync.project_root()
    return {
        "directions": submitted["directions"],
        "frames_per_direction": [len(f) for _, f in polled],
        "sheet_png": str(sheet_png.relative_to(rel_root)),
        "sheet_json": str(sheet_json.relative_to(rel_root)),
        "partial": bool(requested),
    }


# === Stages ===


@stage(asset_type="character", deps=[], throttle="pixellab_bg_job")
async def generate_rotations(ctx: StageContext) -> dict[str, Any]:
    """Pixellab create-character-with-{4,8}-directions → save rotation PNGs."""
    p = ctx.params
    description = ctx.asset.get("description")
    if not description:
        raise RuntimeError(
            f"character {ctx.name} has no description; set asset.description first"
        )
    directions = int(ctx.asset.get("directions") or p.get("directions") or 8)
    token = plab_sync.load_token()

    submit = (
        plab.submit_character_8dir if directions == 8 else plab.submit_character_4dir
    )
    char_id, images = await submit(
        token,
        description,
        view=p.get("view", "high_top_down"),
        proportions_preset=p.get("proportions", "cartoon"),
        isometric=p.get("isometric", False),
    )

    char_dir = manifest.character_dir(ctx.name)
    saved = _save_rotations(images, char_dir)

    # Write character_id + base metadata to asset.json so subsequent stages
    # can find it. status field is legacy/cosmetic; the per-stage status
    # in `stages` dict is the real signal.
    manifest.upsert_character(ctx.name, {
        "character_id": char_id,
        "preset": p.get("preset", "player"),
        "directions": directions,
        "view": p.get("view", "high_top_down"),
        "proportions": p.get("proportions", "cartoon"),
        "isometric": p.get("isometric", False),
        "rotations": list(saved.keys()),
        "local_path": str(char_dir.relative_to(plab_sync.project_root())),
        "status": "base_ready",
    })
    rel_root = plab_sync.project_root()
    return {
        "character_id": char_id,
        "rotation_paths": [str(p.relative_to(rel_root)) for p in saved.values()],
    }


@stage(asset_type="character", deps=["generate_rotations"], throttle="pixellab_bg_job")
async def animate_idle(ctx: StageContext) -> dict[str, Any]:
    """Idle animation via Pixellab template (default: breathing-idle)."""
    template_id = ctx.params.get("idle_template_id") or at.DEFAULT_TEMPLATES["idle"].template_id
    directions = at.DEFAULT_TEMPLATES["idle"].directions
    return await _run_animation(
        ctx, action="idle", template_id=template_id, directions=list(directions),
    )


@stage(asset_type="character", deps=["generate_rotations"], throttle="pixellab_bg_job")
async def animate_walk(ctx: StageContext) -> dict[str, Any]:
    """Walk animation via Pixellab template (default: walking-6-frames).

    Skipped (no-op completion) if character is 4-direction (static NPC),
    since walking implies 8-directional motion.
    """
    directions = int(ctx.asset.get("directions") or 8)
    if directions == 4:
        return {"skipped": True, "reason": "4-dir character (static NPC)"}
    template_id = ctx.params.get("walk_template_id") or at.DEFAULT_TEMPLATES["walk"].template_id
    return await _run_animation(
        ctx, action="walk", template_id=template_id, directions=list(at.DEFAULT_TEMPLATES["walk"].directions),
    )


@stage(asset_type="character", deps=["animate_idle", "animate_walk"])
async def import_to_godot(ctx: StageContext) -> dict[str, Any]:
    """Copy spritesheet PNG + atlas JSON to game/assets/textures/characters/."""
    # Local-only stage; no Pixellab call. Sync I/O wrapped to keep the runner
    # interface uniform (await trivially via asyncio.to_thread).
    def _do_import() -> dict[str, str]:
        from orchestrators import _godot_import as gimport
        char_dir = manifest.character_dir(ctx.name)
        sheet_dir = char_dir / "spritesheet"
        src_png = sheet_dir / f"{ctx.name}.png"
        src_json = sheet_dir / f"{ctx.name}.json"
        if not src_png.exists() or not src_json.exists():
            raise RuntimeError(
                f"spritesheet missing in {sheet_dir}; animate stages must complete first"
            )
        png_dest, json_dest = gimport.import_character_spritesheet(
            src_png=src_png, src_atlas_json=src_json, name=ctx.name
        )
        rel_root = plab_sync.project_root()
        manifest.mark_imported(
            "character",
            ctx.name,
            game_png_path=str(png_dest.relative_to(rel_root)),
            game_json_path=str(json_dest.relative_to(rel_root)),
        )
        return {
            "game_png": str(png_dest.relative_to(rel_root)),
            "game_json": str(json_dest.relative_to(rel_root)),
        }

    return await asyncio.to_thread(_do_import)
