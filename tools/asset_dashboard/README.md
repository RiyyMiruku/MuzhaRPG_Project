# Asset Dashboard

Internal Web UI for browsing art-pipeline output, viewing each asset's stage
progress, and editing/remaking prompts.

## Quick start

```powershell
# 1. Install JS deps (one-time)
cd tools/asset_dashboard/frontend
pnpm install
pnpm build
cd ../../..

# 2. Run the server
uv run uvicorn tools.asset_dashboard.backend.server:app --port 8765
```

Then open http://localhost:8765/.

For frontend dev with hot reload:

```powershell
# Terminal 1: backend
uv run uvicorn tools.asset_dashboard.backend.server:app --reload --port 8765

# Terminal 2: frontend (proxies /api to 8765)
cd tools/asset_dashboard/frontend
pnpm dev
```

Visit http://localhost:5173/.

## What it does

- Reads `pipeline/output/manifest.json`.
- Lists every asset with thumbnail (south rotation / iso PNG / object PNG).
- Filters by chapter (manifest `tags` containing `chapter:N`), asset type, status.
- Shows per-stage prompt. Realized stages are read-only; click `Remake` to unlock.
- Editing an unrealized stage's prompt PATCHes manifest.
- Submitting a Remake POSTs `/api/asset/.../remake` which spawns the matching
  orchestrator with `--force-restart-stage <stage>` and `--resume-from <stage>`.
- A jobs panel (bottom-right) tails subprocess stdout.

## Endpoints

- `GET /api/manifest` — flat asset summaries
- `GET /api/asset/{type}/{name}/thumbnail` — PNG bytes
- `PATCH /api/asset/{type}/{name}/prompts` — update prompt for an unrealized stage
- `POST /api/asset/{type}/{name}/remake` — trigger orchestrator subprocess
- `GET /api/jobs` — list all started jobs
- `GET /api/jobs/{id}` — single job + tail of log

## Limitations

- No multi-user coordination. Two people editing the same asset simultaneously
  will race on manifest writes.
- No undo. Manifest changes are immediate.
- Remake is precise — restarting an early stage does NOT cascade-invalidate
  later stages. The user must re-Remake each downstream stage they want to redo.
- Job state lives only in process memory. Restarting the server forgets job
  history (logs in tmp/ remain).
