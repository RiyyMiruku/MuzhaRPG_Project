"""Stage registry — async pipeline stages, no subprocess.

Every art-pipeline action (generate_rotations, animate_idle, ...) is an
async function decorated with `@stage`. The registry keeps them keyed by
asset_type + stage_name. The worker loop in the backend reads asset.json
files, finds stages whose deps are satisfied, and dispatches them as
asyncio.Task — no subprocess, no log file scraping.

A stage records its lifecycle in the asset's `stages` dict:

    asset.stages["generate_rotations"] = {
      "status": "completed",            # pending|queued|running|completed|failed
      "queued_at":   "2026-05-14T...",
      "started_at":  "2026-05-14T...",
      "completed_at":"2026-05-14T...",
      "result":      {...},             # stage-specific output (paths, IDs)
      "error":       null,              # on failure: traceback summary
    }

Status semantics:
  - pending:    deps not yet completed; can't run
  - queued:     deps completed; waiting for throttle slot
  - running:    worker has started a Task for it
  - completed:  success
  - failed:     unhandled exception; manual retry needed
  - skipped:    explicitly disabled (rare; e.g. --no-idle on static NPC)

Adding a new stage = a single `@stage(...)` decorated function in
pipeline/stages/<asset_type>.py. The runner discovers it automatically.
"""
from __future__ import annotations

import asyncio
import datetime as _dt
import inspect
import traceback
from collections.abc import Callable, Awaitable
from dataclasses import dataclass, field
from typing import Any

import manifest


# === Public types ===


StageFn = Callable[["StageContext"], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class StageDef:
    """Static metadata about a stage. One per @stage-decorated function."""
    name: str
    asset_type: str               # "character" | "object" | "tileset"
    deps: tuple[str, ...]         # other stage names that must be completed
    throttle_category: str | None # acquire slot from this throttle bucket
    fn: StageFn


@dataclass
class StageContext:
    """Passed to each stage function."""
    asset_type: str
    name: str
    asset: dict[str, Any]              # full asset.json contents
    params: dict[str, Any] = field(default_factory=dict)


# === Registry ===


_REGISTRY: dict[tuple[str, str], StageDef] = {}


def stage(
    *,
    asset_type: str,
    deps: list[str] | tuple[str, ...] = (),
    throttle: str | None = None,
) -> Callable[[StageFn], StageFn]:
    """Decorator: register an async function as a pipeline stage.

      @stage(asset_type='character', deps=['generate_rotations'],
             throttle='pixellab_bg_job')
      async def animate_idle(ctx: StageContext) -> dict:
          ...
          return {'frames': N}    # written to asset.stages[name].result
    """
    deps_tuple = tuple(deps)

    def wrap(fn: StageFn) -> StageFn:
        if not inspect.iscoroutinefunction(fn):
            raise TypeError(
                f"@stage function {fn.__name__!r} must be async (await pixellab calls)"
            )
        sd = StageDef(
            name=fn.__name__,
            asset_type=asset_type,
            deps=deps_tuple,
            throttle_category=throttle,
            fn=fn,
        )
        key = (asset_type, fn.__name__)
        if key in _REGISTRY:
            raise RuntimeError(
                f"duplicate stage registration: {asset_type}/{fn.__name__}"
            )
        _REGISTRY[key] = sd
        return fn

    return wrap


def get_stage(asset_type: str, name: str) -> StageDef | None:
    return _REGISTRY.get((asset_type, name))


def stages_for(asset_type: str) -> list[StageDef]:
    """All stages registered for this asset type, in registration order."""
    return [s for (t, _), s in _REGISTRY.items() if t == asset_type]


# === Throttles (async semaphores per category) ===
#
# Categories let different stage types compete for separate quotas.
# Pixellab Tier 1 caps concurrent background jobs at 3, so every
# Pixellab-touching stage shares one bucket. Local-only stages (chroma_key,
# import_to_godot) need no throttle.

_THROTTLES: dict[str, asyncio.Semaphore] = {}
_THROTTLE_LIMITS: dict[str, int] = {
    "pixellab_bg_job": 3,
}


def get_throttle(category: str) -> asyncio.Semaphore:
    if category not in _THROTTLES:
        if category not in _THROTTLE_LIMITS:
            raise KeyError(
                f"unknown throttle category {category!r}; "
                f"register in _THROTTLE_LIMITS first"
            )
        _THROTTLES[category] = asyncio.Semaphore(_THROTTLE_LIMITS[category])
    return _THROTTLES[category]


# === Per-stage state helpers ===


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _stage_state(asset: dict[str, Any], stage_name: str) -> dict[str, Any]:
    return (asset.get("stages") or {}).get(stage_name, {})


def stage_status(asset: dict[str, Any], stage_name: str) -> str:
    """Returns 'pending' for any stage with no recorded state."""
    s = _stage_state(asset, stage_name)
    return s.get("status") or "pending"


def deps_satisfied(asset: dict[str, Any], stage: StageDef) -> bool:
    """True if all deps are status=completed."""
    for d in stage.deps:
        if stage_status(asset, d) != "completed":
            return False
    return True


def ready_stages(asset: dict[str, Any]) -> list[StageDef]:
    """Stages that should be queued: status==pending AND deps satisfied.

    Doesn't transition them to queued — caller (worker loop) decides whether
    to also acquire the throttle slot atomically with the queued write.
    """
    asset_type = asset.get("asset_type")
    if not asset_type:
        return []
    out: list[StageDef] = []
    for sd in stages_for(asset_type):
        if stage_status(asset, sd.name) != "pending":
            continue
        if not deps_satisfied(asset, sd):
            continue
        out.append(sd)
    return out


# === Stage execution ===


def _write_stage_state(
    asset_type: str,
    name: str,
    stage_name: str,
    patch: dict[str, Any],
) -> None:
    """Merge a stage state patch into the asset's asset.json."""
    bucket = manifest._bucket_for(asset_type)
    entry = manifest._read_asset(bucket, name) or {}
    stages = entry.setdefault("stages", {})
    state = stages.setdefault(stage_name, {})
    state.update(patch)
    entry["updated_at"] = _now_iso()
    manifest._write_asset(bucket, name, entry)


def mark_queued(asset_type: str, name: str, stage_name: str) -> None:
    _write_stage_state(asset_type, name, stage_name, {
        "status": "queued",
        "queued_at": _now_iso(),
    })


def mark_running(asset_type: str, name: str, stage_name: str) -> None:
    _write_stage_state(asset_type, name, stage_name, {
        "status": "running",
        "started_at": _now_iso(),
    })


def mark_completed(
    asset_type: str, name: str, stage_name: str, result: dict[str, Any] | None = None
) -> None:
    _write_stage_state(asset_type, name, stage_name, {
        "status": "completed",
        "completed_at": _now_iso(),
        "result": result or {},
        "error": None,
    })


def mark_failed(
    asset_type: str, name: str, stage_name: str, error: str
) -> None:
    _write_stage_state(asset_type, name, stage_name, {
        "status": "failed",
        "failed_at": _now_iso(),
        "error": error,
    })


def reset_stage(asset_type: str, name: str, stage_name: str) -> None:
    """Manual retry: drop a stage's state so the worker re-queues it.
    Caller is responsible for clearing downstream completed stages too if
    they want a cascade re-run."""
    bucket = manifest._bucket_for(asset_type)
    entry = manifest._read_asset(bucket, name) or {}
    stages = entry.get("stages") or {}
    if stage_name in stages:
        del stages[stage_name]
        entry["stages"] = stages
        entry["updated_at"] = _now_iso()
        manifest._write_asset(bucket, name, entry)


async def run_stage(asset_type: str, name: str, stage_name: str) -> None:
    """Execute one stage. Caller has already taken the throttle slot
    (or this is throttle=None). Caller should release after this returns
    or raises.

    Lifecycle: marks running → calls fn → marks completed/failed.
    Re-raises exceptions for the caller's logging; status is recorded
    either way.
    """
    sd = get_stage(asset_type, stage_name)
    if sd is None:
        raise KeyError(f"unknown stage {asset_type}/{stage_name}")

    bucket = manifest._bucket_for(asset_type)
    entry = manifest._read_asset(bucket, name)
    if entry is None:
        raise KeyError(f"asset {asset_type}/{name} not found")

    mark_running(asset_type, name, stage_name)
    ctx = StageContext(
        asset_type=asset_type,
        name=name,
        asset=entry,
        params=entry.get("params", {}),
    )
    try:
        result = await sd.fn(ctx)
    except Exception as e:
        tb = traceback.format_exc(limit=10)
        mark_failed(asset_type, name, stage_name, f"{type(e).__name__}: {e}\n{tb}")
        raise
    mark_completed(asset_type, name, stage_name, result if isinstance(result, dict) else None)


__all__ = [
    "StageDef",
    "StageContext",
    "stage",
    "get_stage",
    "stages_for",
    "ready_stages",
    "stage_status",
    "deps_satisfied",
    "get_throttle",
    "mark_queued",
    "mark_running",
    "mark_completed",
    "mark_failed",
    "reset_stage",
    "run_stage",
]
