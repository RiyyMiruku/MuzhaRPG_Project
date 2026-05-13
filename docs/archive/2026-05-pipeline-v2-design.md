# Pipeline v2 Redesign — File-per-Asset + Single Async Backend

> Date: 2026-05-14
> Branch (planned): `pipeline-v2`
> Author: derived from session debugging chapter 1 art generation
> Status: design approved, Phase 1 in progress

## TL;DR

Replace the current split architecture (`pipeline/orchestrators/*.py` CLI subprocesses + `tools/asset_dashboard/backend/` separate service + `art_source/manifest.json` shared mutable state) with a **single FastAPI backend** that owns:

- **File-per-asset manifest** (`art_source/<type>/<name>/asset.json`)
- **Stage registry** (decorated async functions, no subprocess)
- **Worker loop** that polls per-asset manifest for `status=queued` rows and runs ready stages respecting throttle
- **CLI = thin HTTP client** (no separate execution path)

CLI / Web UI / Skill / agent all hit the same REST endpoints. There is no second way to launch work.

---

## Why

This session surfaced the same root cause from many angles:

| Pain point | Cost |
|---|---|
| `art_source/manifest.json` corrupted by concurrent `/api/asset/create` writes | 30 min recovery + manual JSON repair |
| Pixellab quota cascading 30 jobs to fail in 7s | wasted dashboard slots, confused state |
| CLI-launched orchestrator invisible in dashboard job queue | repeated user friction this session |
| Adding `--isometric` / `--idle-template-id` flag = touch 4 files (`pixellab_client`, `_common`, `npc_moving`, `npc_static`) plus dashboard API drift | template mode shipped but dashboard `/create` still can't request it |
| Subprocess crash leaks Pixellab orphan jobs (no parent to retry) | tokens / quota waste, manual cleanup |
| Test assets (`test_*` prefix) mixed with chapter assets in same manifest | brittle filtering, accidental modification |
| `JobRegistry` in-memory → backend restart loses every in-flight job | manual cleanup, dashboard out of sync with reality |

All of these stem from **two execution paths** (CLI subprocess vs Dashboard backend) writing to **two state stores** (manifest.json + in-memory JobRegistry) coordinated through **fragile contracts** (subprocess cmd args, log file scraping, polling).

The fundamental simplicity hidden underneath: every asset is a small DAG of Pixellab API calls. We don't need subprocesses or two state stores to express that.

---

## Target architecture

```
┌────────────────────────────────────────────────────────────────┐
│ pipeline/server.py  (FastAPI + asyncio worker loop)           │
│                                                                │
│  REST routes:                                                  │
│    POST   /api/asset/{type}/{name}                             │
│      body: {description, params, ...} — upsert + enqueue       │
│    POST   /api/asset/{type}/{name}/stage/{stage}/retry         │
│      body: {only_directions?: [...]}                           │
│    DELETE /api/asset/{type}/{name}                             │
│    GET    /api/manifest          ← aggregate read              │
│    GET    /api/asset/{type}/{name}                             │
│    WS     /api/stream            ← live progress push          │
│                                                                │
│  Worker loop (async):                                          │
│    every tick:                                                 │
│      for asset in manifest.iter():                             │
│        for stage in ready_stages(asset):                       │
│          if throttle.acquire(stage.throttle_category):         │
│            asyncio.create_task(run_stage(asset, stage))        │
│                                                                │
│  Stage registry (decorator):                                   │
│    @stage(asset_type='character', deps=[],                     │
│           throttle='pixellab_bg_job')                          │
│    async def generate_rotations(asset, params): ...            │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                  art_source/<type>/<name>/asset.json
                           │
              ┌────────────┼────────────┐
              │            │            │
       Web UI (React)   CLI client   Skill / agent
       ws + http         http only     http only
```

### Manifest layout (file-per-asset)

```
art_source/
├── characters/
│   ├── player/
│   │   ├── asset.json         ← metadata: status, char_id, stages, tags, prompts
│   │   ├── rotations/
│   │   │   ├── south.png
│   │   │   └── ...
│   │   └── spritesheet/
│   │       ├── player.png
│   │       └── player.json
│   └── lin_siqian/
│       └── ...
├── objects/
│   └── family_photo_blacked/
│       ├── asset.json
│       └── family_photo_blacked.png
└── tilesets/
    └── courtyard_dirt_grass/
        ├── asset.json
        ├── courtyard_dirt_grass_topdown.png
        └── courtyard_dirt_grass_iso.png
```

Each `asset.json` is independent, atomic-renamed on write, no fcntl needed. Concurrent writes to different assets cannot collide. Per-asset diff in git PRs is one file per asset that changed.

Reading "all assets" = walk `art_source/{characters,objects,tilesets}/*/asset.json` (~500 files at peak, ~50 ms with parallel I/O).

### Stage registry

```python
# pipeline/stages/character.py
from pipeline.stages import stage
from pipeline import pixellab

@stage(asset_type='character', deps=[], throttle='pixellab_bg_job')
async def generate_rotations(asset, params):
    char_id, images = await pixellab.create_character(
        directions=asset.directions,
        description=asset.description,
        isometric=params.get('isometric', False),
        view=params.get('view', 'high_top_down'),
    )
    asset.character_id = char_id
    save_rotations(images, asset.path / 'rotations')

@stage(asset_type='character', deps=['generate_rotations'], throttle='pixellab_bg_job')
async def animate_idle(asset, params):
    template = params.get('idle_template_id', 'breathing-idle')
    await pixellab.animate(asset.character_id, template=template, directions=CARDINAL_4)

@stage(asset_type='character', deps=['generate_rotations'], throttle='pixellab_bg_job')
async def animate_walk(asset, params):
    template = params.get('walk_template_id', 'walking-6-frames')
    await pixellab.animate(asset.character_id, template=template, directions=ALL_8)

@stage(asset_type='character', deps=['animate_idle', 'animate_walk'])
async def import_to_godot(asset, params):
    spritesheet = compile_sheet(asset.path)
    copy_to_godot(spritesheet, name=asset.name)
```

Adding a new animation (e.g., `running`) = add a single decorated function. The runner picks it up automatically because the stage registry is global.

`animate_idle` and `animate_walk` have no dependency on each other, so they run in parallel (subject to throttle).

### Throttle

In-process semaphore per category:

```python
THROTTLES = {
    'pixellab_bg_job': asyncio.Semaphore(3),  # respect Pixellab Tier 1 limit
}
```

When the worker loop dispatches a stage, it `acquire()`s before `create_task` and `release()`s in `finally`. Single source of truth for concurrency, applies across all asset types and all callers.

### State machine per asset

```
created  ─▶  queued  ─▶  running  ─▶  completed
                              │
                              ╰─▶  failed
```

Per-stage:
```python
asset.stages = {
    'generate_rotations': {'status': 'completed', 'completed_at': ..., 'paths': [...]},
    'animate_idle':       {'status': 'queued'},
    'animate_walk':       {'status': 'running', 'started_at': ...},
    'import_to_godot':    {'status': 'pending'},  # deps not yet satisfied
}
```

Worker loop transitions: `pending` → `queued` (when deps met) → `running` (when slot free) → `completed`/`failed`.

**Resume / partial regen** is just setting a stage's status back to `queued`. UI button: "Retry stage" or "Retry direction X" → backend writes status, worker picks up.

---

## What dies

| Removed | Reason |
|---|---|
| `pipeline/orchestrators/{npc_moving,npc_static,prop,autotile,_common,_godot_import}.py` | Logic absorbed into `pipeline/stages/*.py` async functions |
| `tools/asset_dashboard/backend/jobs.py` `JobRegistry` class | Manifest IS the queue |
| `subprocess.Popen` + log file + reaper | No subprocess; direct async call |
| `pipeline/manifest.py` `_locked_update()` + fcntl | Single-file-per-asset means no shared file = no lock needed |
| `--review-mode stage` (one-stage-at-a-time interactive mode) | Replaced by UI: stage progress visible live, manual retry per stage |
| Idea of `dashboard_register` / `register_external` (proposed but reverted) | Not needed; CLI uses HTTP, not subprocess |
| Skill `art-pipeline` ~200 lines of CLI vs API decision logic | Becomes ~30 lines: "POST to API. Done." |

## What survives

| Kept | Notes |
|---|---|
| `pipeline/pixellab_client.py` core HTTP wrapper | Renamed `pipeline/pixellab.py`; full async (httpx) |
| 429 retry + quota-job retry + template-mode plumbing | Migrated as-is |
| `pipeline/animation_templates.py` registry | Becomes default params on stage decorator |
| `pipeline/spritesheet.py` / `pipeline/post_process.py` | Pure helpers, no change |
| React frontend (`tools/asset_dashboard/frontend/`) | Re-point base URL + add WebSocket subscription for live status |
| `story/chapters/*/assets.json` chapter declarations | Becomes batch upload payload to `POST /api/assets/batch` |
| Pixellab redoc scrape tool (`tools/scrape_pixellab_docs.py`) | Unchanged |

---

## Phasing

Phasing is conservative — each phase shippable + reversible.

### Phase 1: file-per-asset manifest (foundation, no behavior change)

**Goal**: replace `art_source/manifest.json` with per-asset `asset.json` files. Old orchestrators + dashboard continue to work, just reading/writing through new layer.

- 1a: Rewrite `pipeline/manifest.py`. Same public API (`upsert_character`, `mark_stage`, `add_tags`, `get_*`, `query_assets` etc.) but reads/writes per-asset files.
- 1b: Migration script converts `art_source/manifest.json` into per-asset `asset.json` files. Idempotent, runnable any time.
- 1c: `tools/asset_dashboard/backend/manifest_io.py` adapter to aggregate per-asset files into the same shape the frontend already expects (no frontend change).
- 1d: Run migration, verify dashboard renders correctly, smoke test create + remake.

**Reversible**: keep old `manifest.json` as `.bak` until phase 1 is committed and CI green.

### Phase 2: stage registry + async backend (the big change)

**Goal**: stages run in-process inside dashboard backend instead of as subprocesses.

- 2a: New `pipeline/stages/__init__.py` with `@stage` decorator + registry.
- 2b: Translate each existing orchestrator stage to async function in `pipeline/stages/{character,object,tileset}.py`.
- 2c: Async-ify `pipeline/pixellab.py` (use `httpx.AsyncClient`).
- 2d: New worker loop in backend; remove `JobRegistry`.
- 2e: New REST routes; map old `/api/asset/create` + `/remake` to new ones (compat shim until callers migrate).
- 2f: Delete `pipeline/orchestrators/` once parity confirmed.

### Phase 3: CLI = HTTP client + WebSocket

- 3a: `pipeline/cli.py` thin client (`python -m pipeline create character ...` → HTTP).
- 3b: WebSocket endpoint for live stage status; frontend subscribes.
- 3c: Skill `art-pipeline` rewrite (drops to ~30 lines).

### Phase 4: cleanup

- Remove compat shims, deprecated routes, old manifest.json fallback.
- Migrate any remaining unmigrated entries.

---

## Risk and migration safety

| Risk | Mitigation |
|---|---|
| Migration loses asset metadata | Backup `manifest.json` → `manifest.json.bak-vN` before each migration; keep for one release |
| Backend crash mid-Pixellab-poll leaks orphan job | Worker startup scans `status=running` entries with no `started_at < now-1h`, marks `failed` |
| File-per-asset can't do "list all chapter:1 status:running" efficiently | Acceptable: ~500 files × `json.load` = milliseconds. If it ever matters, add `art_source/.cache/index.json` rebuilt from per-asset files |
| Two backends running concurrently (dev + production) write to same `art_source/` | Same problem as today; out of scope |
| Frontend assumes old aggregate shape | Phase 1c adapter preserves it; phase 3 frontend rewrite when ready |
| Chapter creation flow (`assets.json` → batch create) breaks | Phase 1 batch endpoint accepts the same JSON shape |

---

## Non-goals (explicitly not solving here)

- Multi-machine / distributed pipeline (single backend assumed)
- Database migrations across schema changes (per-asset JSON is forgiving; add new fields freely, default-on-read)
- Authentication / multi-tenant (single user, local dev tool)
- Production deployment (this is a creative tool, not a service)

---

## Decision log (questions resolved during design)

| Q | Decision | Reason |
|---|---|---|
| SQLite vs JSON-per-asset vs single JSON? | **JSON-per-asset** | Git diff friendliness, no schema migration burden, scale (≤500 assets) makes SQL querying overkill |
| Subprocess per asset vs in-process async? | **in-process async** | No subprocess crashes leaking orphan Pixellab jobs; one event loop handles N concurrent Pixellab polls |
| Keep CLI as standalone? | **No, CLI = HTTP client** | Eliminates "this job didn't appear in dashboard" entirely |
| Keep `--review-mode stage` interactive? | **No** | UI live progress + per-stage retry button replaces it |
| Backend → frontend live updates: SSE or WS? | **WS** | Bi-directional (UI sends "retry"); already proven in dashboard ecosystem |
| Inline stage params in asset.json or separate? | **Inline** | Asset is the unit; params drift with asset; one less file |

---

## What this session learned that survived to v2

- Pixellab two 429 paths (POST + poll-failure) → both retry paths preserved in `pipeline/pixellab.py`
- Pixellab Tier 1 max 3 concurrent background jobs → `THROTTLES['pixellab_bg_job'] = Semaphore(3)`
- Template mode (breathing-idle / walking-6-frames) > v3 prompt-driven → templates are stage default params
- No isometric building endpoint, but `/v2/create-image-pixflux` `isometric: true` works → `pipeline/stages/object.py` has separate iso path for buildings
- Redoc more accurate than llms.txt for Pixellab docs → unchanged, scrape tool kept

See:
- [memory/pixellab-quota-two-paths](../../.claude/projects/-Users-JustinCheng-Documents-GitHub-MuzhaRPG-Project/memory/pixellab_quota_two_paths.md)
- [memory/pixellab-isometric-options-for-buildings](../../.claude/projects/-Users-JustinCheng-Documents-GitHub-MuzhaRPG-Project/memory/pixellab_isometric_options_for_buildings.md)
- [memory/manifest-needs-file-lock](../../.claude/projects/-Users-JustinCheng-Documents-GitHub-MuzhaRPG-Project/memory/manifest_needs_file_lock.md) (Phase 1 supersedes; the lock is no longer needed once each writer has its own file)
