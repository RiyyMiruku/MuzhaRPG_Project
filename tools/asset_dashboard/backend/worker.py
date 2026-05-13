"""V2 worker loop: scans per-asset asset.json files, dispatches ready stages.

Runs as a background asyncio task started during FastAPI lifespan. Polls
manifest every WORKER_TICK_SECONDS, finds stages where:
  - status is unset/'pending'
  - all dependencies have status='completed'

It marks them 'queued' immediately, then tries to acquire the throttle
slot for that stage's category. If acquired, dispatches a Task that runs
the stage and releases on completion. If not acquired, the stage stays
'queued' and the next tick retries.

Self-healing: stages stuck in 'running' across a backend restart are
detected (no in-memory task tracking them) and reset to 'pending' so the
worker re-dispatches.
"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "pipeline"))

import manifest  # noqa: E402
import stages as stages_mod  # noqa: E402
import stages.character  # noqa: E402,F401  — registers character stages

log = logging.getLogger("dashboard.worker")
# Inherit stdout from uvicorn's root config (INFO+) instead of disappearing.
log.setLevel(logging.INFO)
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[worker] %(asctime)s %(levelname)s %(message)s"))
    log.addHandler(_h)
    log.propagate = False

WORKER_TICK_SECONDS = 2.0

# Track tasks dispatched in this process so a backend restart can reset
# 'running' stages whose driving task is gone.
_running_keys: set[tuple[str, str, str]] = set()  # (asset_type, name, stage_name)


def _key(asset_type: str, name: str, stage_name: str) -> tuple[str, str, str]:
    return (asset_type, name, stage_name)


async def _run_and_release(
    asset_type: str, name: str, stage_name: str, throttle: asyncio.Semaphore | None
) -> None:
    key = _key(asset_type, name, stage_name)
    _running_keys.add(key)
    try:
        await stages_mod.run_stage(asset_type, name, stage_name)
    except Exception as e:
        log.error("[stage failed] %s/%s/%s: %s", asset_type, name, stage_name, e)
    finally:
        _running_keys.discard(key)
        if throttle is not None:
            throttle.release()


def _reset_orphan_running(data: dict) -> int:
    """On worker startup: v2 stages marked 'running' but no task driving
    them are leftovers from a previous backend instance. Reset to pending
    so worker re-queues. ONLY touches v2-opted-in assets — legacy assets
    have their own stage state that this worker must not corrupt."""
    reset = 0
    for bucket, asset_type in (("characters", "character"), ("tilesets", "tileset"), ("objects", "object")):
        for asset_name, entry in (data.get(bucket) or {}).items():
            if not _is_v2_opted_in(entry):
                continue
            for stage_name, state in (entry.get("stages") or {}).items():
                if state.get("status") != "running":
                    continue
                if _key(asset_type, asset_name, stage_name) in _running_keys:
                    continue
                # Only reset stages registered as v2 stages (don't touch
                # legacy-named entries that may coexist on opted-in assets
                # for some transition period).
                if stages_mod.get_stage(asset_type, stage_name) is None:
                    continue
                stages_mod.reset_stage(asset_type, asset_name, stage_name)
                log.warning(
                    "[orphan reset] %s/%s/%s was 'running' with no task; "
                    "reset to pending", asset_type, asset_name, stage_name,
                )
                reset += 1
    return reset


def _is_dispatchable(asset: dict, stage_name: str) -> bool:
    """A stage is fresh (pending) OR was queued in a prior tick but hasn't
    started yet (no task in this process drives it)."""
    status = stages_mod.stage_status(asset, stage_name)
    if status == "pending":
        return True
    if status == "queued":
        # If a Task already exists for it, leave alone; otherwise re-dispatch.
        return _key(asset.get("asset_type", ""), asset.get("__name", ""), stage_name) not in _running_keys
    return False


# v2 worker opts in per-asset. Legacy assets (created via subprocess
# orchestrators) have stage names like 'generate_8dir_base' / 'add_idle_animation'
# that DO NOT match v2 names ('generate_rotations' / 'animate_idle'), so
# without an opt-in marker the worker would treat every legacy completed
# asset as "pending all v2 stages" and re-run the whole pipeline against
# Pixellab — destroying the existing char_id binding and wasting tokens.
# Marker: asset.json must have `pipeline_version >= 2`.
_V2_OPT_IN_KEY = "pipeline_version"
_V2_OPT_IN_MIN = 2


def _is_v2_opted_in(entry: dict) -> bool:
    return int(entry.get(_V2_OPT_IN_KEY, 1)) >= _V2_OPT_IN_MIN


async def _tick() -> None:
    """One pass over the manifest. Dispatch ready stages respecting throttle.

    Only considers assets opted into v2 (pipeline_version >= 2). Legacy
    assets are owned by the subprocess+JobRegistry path and are invisible
    to the v2 worker.
    """
    data = manifest.load()
    for bucket, asset_type in (("characters", "character"), ("tilesets", "tileset"), ("objects", "object")):
        for asset_name, entry in (data.get(bucket) or {}).items():
            if not _is_v2_opted_in(entry):
                continue
            entry_with_type = {**entry, "asset_type": asset_type, "__name": asset_name}
            for sd in stages_mod.stages_for(asset_type):
                status = stages_mod.stage_status(entry_with_type, sd.name)
                if status not in ("pending", "queued"):
                    continue
                if status == "queued" and _key(asset_type, asset_name, sd.name) in _running_keys:
                    continue
                if not stages_mod.deps_satisfied(entry_with_type, sd):
                    continue

                if status == "pending":
                    stages_mod.mark_queued(asset_type, asset_name, sd.name)

                throttle = (
                    stages_mod.get_throttle(sd.throttle_category)
                    if sd.throttle_category else None
                )
                if throttle is not None and throttle.locked():
                    continue
                if throttle is not None:
                    await throttle.acquire()
                asyncio.create_task(
                    _run_and_release(asset_type, asset_name, sd.name, throttle)
                )


async def worker_loop() -> None:
    """Forever loop. Started by FastAPI lifespan; cancelled on shutdown."""
    # Startup: reset any orphan 'running' from previous backend instance.
    _reset_orphan_running(manifest.load())
    log.info("worker loop started")
    try:
        while True:
            try:
                await _tick()
            except Exception as e:
                log.exception("worker tick failed (continuing): %s", e)
            await asyncio.sleep(WORKER_TICK_SECONDS)
    except asyncio.CancelledError:
        log.info("worker loop shutting down")
        raise


__all__ = ["worker_loop"]
