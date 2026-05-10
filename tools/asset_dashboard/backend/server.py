# tools/asset_dashboard/backend/server.py
"""FastAPI app for the asset dashboard.

Run: uv run uvicorn tools.asset_dashboard.backend.server:app --reload --port 8765
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .manifest_io import load_assets

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "art_source" / "pipeline" / "output" / "manifest.json"

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
