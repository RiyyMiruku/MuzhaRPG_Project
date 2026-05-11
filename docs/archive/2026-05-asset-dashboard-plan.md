# Asset Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 內部 Web UI 給美術組瀏覽 art-pipeline 產出的資產、查看每個資產的 stage 進度、檢視已實現的 prompt、編輯尚未實現的 prompt、按 Remake 對既有 stage 重新生成。

**Architecture:** FastAPI backend serve manifest JSON + thumbnail bytes + 觸發 orchestrator subprocess。Vite + React + TypeScript + Tailwind frontend 在 dev 用 Vite proxy,production build 後由 FastAPI 一起 serve。Manifest schema 擴展新增 `prompts` 區塊(per-stage prompt),orchestrator 從 manifest 讀 prompt 取代既有寫死的 `"idle"` / `"walk"`。Remake 採精準模式 — 只強制重跑該 stage,下游不自動失效。

**Tech Stack:** Python 3.13 + FastAPI + uvicorn(backend);Vite + React 18 + TypeScript + Tailwind v3 + lucide-react(frontend);pnpm 包管;subprocess 跑既有 orchestrator;pytest + httpx(backend test)。

---

## File Structure

```
tools/asset_dashboard/
├── backend/
│   ├── __init__.py
│   ├── server.py           ← FastAPI app + 路由
│   ├── jobs.py             ← subprocess 啟動 + 狀態追蹤(in-memory dict)
│   ├── manifest_io.py      ← 讀寫 manifest.json + tag/prompt helper
│   └── thumbnails.py       ← 依資產類型挑代表縮圖
├── frontend/
│   ├── package.json        ← pnpm 依賴
│   ├── pnpm-lock.yaml      ← 鎖檔(install 後產生)
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   ├── vite.config.ts      ← dev proxy /api → backend 8765
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api.ts          ← fetch wrapper + 型別
│       ├── types.ts        ← Asset / Stage / Prompt TS interfaces
│       ├── index.css       ← Tailwind import
│       └── components/
│           ├── FilterBar.tsx
│           ├── AssetGrid.tsx
│           ├── AssetCard.tsx
│           ├── StageList.tsx
│           ├── PromptEditor.tsx
│           └── JobLogPanel.tsx
├── tests/
│   ├── __init__.py
│   ├── test_manifest_io.py
│   ├── test_jobs.py
│   ├── test_thumbnails.py
│   └── test_server.py
└── README.md

art_source/pipeline/
├── manifest.py             ← 修改:新增 prompts 欄位 helper
└── orchestrators/
    ├── npc_static.py       ← 修改:從 manifest 讀 prompts
    ├── npc_moving.py       ← 修改:同上
    ├── prop.py             ← 修改:同上
    └── autotile.py         ← 修改:同上
```

**Manifest schema 擴展(per-asset):**

```json
{
  "<name>": {
    "...既有欄位": "...",
    "tags": ["zone:shared", "category:player", "chapter:1"],
    "prompts": {
      "<stage_name>": "<prompt text>"
    }
  }
}
```

`prompts` 是 dict;key 是 stage 名(`generate_8dir_base`、`add_idle_animation` 等)。Stage 1 的 prompt 從既有 `description` 欄位 lazy-migrate(讀時若 prompts 缺該 key 則 fallback `description`)。後續階段(`add_idle_animation` / `add_walk_animation`)新增。

---

## Task 1: Manifest prompts 欄位 + helper

**Files:**
- Modify: `art_source/pipeline/manifest.py`
- Test: `tools/asset_dashboard/tests/test_manifest_io.py`(這個檔在 Task 4 才建,本 task 用既有 pipeline 測)
- Test: `art_source/pipeline/tests/test_manifest_prompts.py` ← 新建

- [ ] **Step 1: Write failing test for `get_prompt` / `set_prompt` / `list_prompts`**

```python
# art_source/pipeline/tests/test_manifest_prompts.py
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import manifest


def test_get_prompt_returns_stored(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "MANIFEST_PATH", tmp_path / "m.json")
    manifest.save_manifest({
        "version": 1,
        "characters": {
            "alice": {
                "description": "fallback text",
                "prompts": {"generate_8dir_base": "explicit"},
            }
        },
        "tilesets": {}, "objects": {},
    })
    assert manifest.get_prompt("character", "alice", "generate_8dir_base") == "explicit"


def test_get_prompt_falls_back_to_description(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "MANIFEST_PATH", tmp_path / "m.json")
    manifest.save_manifest({
        "version": 1,
        "characters": {
            "alice": {"description": "old style", "prompts": {}},
        },
        "tilesets": {}, "objects": {},
    })
    assert manifest.get_prompt("character", "alice", "generate_8dir_base") == "old style"


def test_get_prompt_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "MANIFEST_PATH", tmp_path / "m.json")
    manifest.save_manifest({
        "version": 1,
        "characters": {"alice": {}},
        "tilesets": {}, "objects": {},
    })
    assert manifest.get_prompt("character", "alice", "add_idle_animation") is None


def test_set_prompt_writes_through(tmp_path, monkeypatch):
    mpath = tmp_path / "m.json"
    monkeypatch.setattr(manifest, "MANIFEST_PATH", mpath)
    manifest.save_manifest({
        "version": 1,
        "characters": {"alice": {}},
        "tilesets": {}, "objects": {},
    })
    manifest.set_prompt("character", "alice", "add_idle_animation", "smoking calmly")
    data = json.loads(mpath.read_text(encoding="utf-8"))
    assert data["characters"]["alice"]["prompts"]["add_idle_animation"] == "smoking calmly"


def test_list_prompts_for_asset(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "MANIFEST_PATH", tmp_path / "m.json")
    manifest.save_manifest({
        "version": 1,
        "characters": {
            "alice": {
                "description": "base",
                "prompts": {"add_idle_animation": "idle calm"},
            }
        },
        "tilesets": {}, "objects": {},
    })
    prompts = manifest.list_prompts("character", "alice")
    assert prompts == {"add_idle_animation": "idle calm"}


def test_set_prompt_unknown_asset_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(manifest, "MANIFEST_PATH", tmp_path / "m.json")
    manifest.save_manifest({"version": 1, "characters": {}, "tilesets": {}, "objects": {}})
    import pytest
    with pytest.raises(KeyError):
        manifest.set_prompt("character", "nobody", "stage", "x")
```

- [ ] **Step 2: Run test to verify failure**

Run: `uv run pytest art_source/pipeline/tests/test_manifest_prompts.py -v`
Expected: FAIL — `AttributeError: module 'manifest' has no attribute 'get_prompt'`

- [ ] **Step 3: Implement helpers in manifest.py**

Append after the existing `mark_imported` function:

```python
# === Prompt management ===

_BUCKET_FOR_TYPE: dict[str, str] = {
    "character": "characters",
    "tileset": "tilesets",
    "object": "objects",
}


def _bucket_for(asset_type: str) -> str:
    if asset_type not in _BUCKET_FOR_TYPE:
        raise ValueError(f"unknown asset_type: {asset_type!r}")
    return _BUCKET_FOR_TYPE[asset_type]


def get_prompt(asset_type: str, name: str, stage: str) -> str | None:
    """讀指定 stage 的 prompt。falls back 到 description(stage 1 兼容舊資產)。"""
    bucket = _bucket_for(asset_type)
    data = load_manifest()
    asset = data.get(bucket, {}).get(name)
    if asset is None:
        return None
    prompts = asset.get("prompts") or {}
    if stage in prompts:
        return prompts[stage]
    if stage in {"generate_8dir_base", "generate_4dir_base", "generate_object", "generate_atlas"}:
        return asset.get("description")
    return None


def list_prompts(asset_type: str, name: str) -> dict[str, str]:
    """回傳該資產所有已存的 prompts(不含 description fallback)。"""
    bucket = _bucket_for(asset_type)
    data = load_manifest()
    asset = data.get(bucket, {}).get(name)
    if asset is None:
        return {}
    return dict(asset.get("prompts") or {})


def set_prompt(asset_type: str, name: str, stage: str, prompt: str) -> None:
    """寫入指定 stage 的 prompt。資產必須已存在。"""
    bucket = _bucket_for(asset_type)
    data = load_manifest()
    asset = data.get(bucket, {}).get(name)
    if asset is None:
        raise KeyError(f"{asset_type} {name!r} not in manifest")
    prompts = dict(asset.get("prompts") or {})
    prompts[stage] = prompt
    asset["prompts"] = prompts
    save_manifest(data)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `uv run pytest art_source/pipeline/tests/test_manifest_prompts.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add art_source/pipeline/manifest.py art_source/pipeline/tests/test_manifest_prompts.py
git commit -m "feat(manifest): per-stage prompts with description fallback for legacy assets"
```

---

## Task 2: Orchestrators 從 manifest 讀 stage prompt

**Files:**
- Modify: `art_source/pipeline/orchestrators/_common.py`
- Modify: `art_source/pipeline/orchestrators/npc_moving.py`
- Modify: `art_source/pipeline/orchestrators/npc_static.py`

`run_character_animation` 目前接 `action: str`(`"idle"` / `"walk"`)當 prompt。改成從 manifest 讀 `prompts[stage_name]`,fallback 既有的 action 字串(無破壞性)。

- [ ] **Step 1: Modify `_common.py` `run_character_animation`**

Change:
```python
def run_character_animation(
    ctx: StageContext,
    action: str,
    directions: list[str],
    frame_count: int,
) -> list[str]:
```

Add a new `stage_name` keyword arg and use it to look up prompt:

Replace the function signature + first lines. Find:

```python
def run_character_animation(
    ctx: StageContext,
    action: str,
    directions: list[str],
    frame_count: int,
) -> list[str]:
```

Replace with:

```python
def run_character_animation(
    ctx: StageContext,
    action: str,
    directions: list[str],
    frame_count: int,
    *,
    stage_name: str | None = None,
) -> list[str]:
    """執行 character animation:submit job → poll 每方向 → 存 frame → 寫 manifest。

    `action` 是預設 prompt(供 fallback 與 Pixellab API 的 action_description 欄位)。
    若 `stage_name` 提供且 manifest 內有該 stage 的 prompt,則用 prompt 取代 action 當作
    送給 Pixellab 的 action_description。
    """
```

In the body, find:

```python
    submitted = plab.submit_character_animation(
        token=token,
        character_id=char_id,
        action_description=action,
        directions=directions,
        frame_count=frame_count,
    )
```

Replace with:

```python
    action_description = action
    if stage_name is not None:
        from_manifest = manifest.get_prompt(ctx.asset_type, ctx.name, stage_name)
        if from_manifest:
            action_description = from_manifest
    submitted = plab.submit_character_animation(
        token=token,
        character_id=char_id,
        action_description=action_description,
        directions=directions,
        frame_count=frame_count,
    )
```

- [ ] **Step 2: Update callers in `npc_moving.py`**

Find both stage definitions and add `stage_name=` to the call. The file currently calls `run_character_animation` from inside `add_idle_animation` and `add_walk_animation`.

In `add_idle_animation`:

```python
return run_character_animation(ctx, "idle", CARDINAL_DIRECTIONS, args.idle_frame_count)
```

Replace with:

```python
return run_character_animation(
    ctx, "idle", CARDINAL_DIRECTIONS, args.idle_frame_count,
    stage_name="add_idle_animation",
)
```

In `add_walk_animation`:

```python
return run_character_animation(ctx, "walk", ALL_8_DIRECTIONS, args.walk_frame_count)
```

Replace with:

```python
return run_character_animation(
    ctx, "walk", ALL_8_DIRECTIONS, args.walk_frame_count,
    stage_name="add_walk_animation",
)
```

- [ ] **Step 3: Update `npc_static.py`'s `add_idle_animation`**

Find:

```python
return run_character_animation(ctx, "idle", CARDINAL_DIRECTIONS, args.idle_frame_count)
```

Replace with:

```python
return run_character_animation(
    ctx, "idle", CARDINAL_DIRECTIONS, args.idle_frame_count,
    stage_name="add_idle_animation",
)
```

- [ ] **Step 4: Smoke-import all four orchestrators**

Run:
```powershell
uv run python -c "import sys; sys.path.insert(0, 'art_source/pipeline/orchestrators'); import npc_static, npc_moving, prop, autotile; print('ok')"
```
Expected: `ok` printed.

- [ ] **Step 5: Commit**

```bash
git add art_source/pipeline/orchestrators/_common.py art_source/pipeline/orchestrators/npc_moving.py art_source/pipeline/orchestrators/npc_static.py
git commit -m "feat(orchestrators): read animation prompts from manifest with fallback"
```

---

## Task 3: Backend skeleton — FastAPI app + manifest read endpoint

**Files:**
- Create: `tools/asset_dashboard/__init__.py`
- Create: `tools/asset_dashboard/backend/__init__.py`
- Create: `tools/asset_dashboard/backend/manifest_io.py`
- Create: `tools/asset_dashboard/backend/server.py`
- Create: `tools/asset_dashboard/tests/__init__.py`
- Create: `tools/asset_dashboard/tests/test_manifest_io.py`
- Create: `tools/asset_dashboard/tests/test_server.py`

- [ ] **Step 1: Add FastAPI dependencies via uv**

Run: `uv add fastapi uvicorn[standard] httpx pytest-asyncio`
Expected: pyproject.toml gets the four packages.

- [ ] **Step 2: Write empty `__init__.py` files**

Create three empty files:
- `tools/asset_dashboard/__init__.py`
- `tools/asset_dashboard/backend/__init__.py`
- `tools/asset_dashboard/tests/__init__.py`

Each contains a single comment line:
```python
# Asset Dashboard package marker.
```

- [ ] **Step 3: Write failing test for manifest_io**

```python
# tools/asset_dashboard/tests/test_manifest_io.py
import json
from pathlib import Path

import pytest

from tools.asset_dashboard.backend.manifest_io import (
    load_assets,
    AssetSummary,
)


def _write_manifest(path: Path, content: dict) -> None:
    path.write_text(json.dumps(content), encoding="utf-8")


def test_load_assets_returns_one_asset_per_entry(tmp_path):
    mpath = tmp_path / "manifest.json"
    _write_manifest(mpath, {
        "version": 1,
        "characters": {
            "alice": {
                "description": "alice the witch",
                "tags": ["zone:nccu", "chapter:1"],
                "stages": {"generate_8dir_base": {"completed_at": "2026-01-01"}},
                "prompts": {"add_idle_animation": "casting"},
            }
        },
        "tilesets": {
            "grass_to_dirt": {
                "description": "natural transition",
                "tags": ["zone:market"],
                "stages": {},
            }
        },
        "objects": {},
    })

    assets = load_assets(mpath)
    assert len(assets) == 2
    by_name = {a.name: a for a in assets}
    assert by_name["alice"].asset_type == "character"
    assert by_name["alice"].chapter == "1"
    assert by_name["alice"].zone == "nccu"
    assert by_name["alice"].completed_stages == ["generate_8dir_base"]
    assert by_name["alice"].prompts == {"add_idle_animation": "casting"}
    assert by_name["grass_to_dirt"].asset_type == "tileset"
    assert by_name["grass_to_dirt"].chapter is None


def test_load_assets_handles_missing_optional_fields(tmp_path):
    mpath = tmp_path / "manifest.json"
    _write_manifest(mpath, {
        "version": 1,
        "characters": {"bob": {}},
        "tilesets": {},
        "objects": {},
    })
    assets = load_assets(mpath)
    assert len(assets) == 1
    a = assets[0]
    assert a.name == "bob"
    assert a.tags == []
    assert a.completed_stages == []
    assert a.prompts == {}


def test_asset_summary_serializes_to_dict():
    s = AssetSummary(
        name="alice",
        asset_type="character",
        description="x",
        tags=["zone:a", "chapter:2"],
        zone="a",
        category=None,
        chapter="2",
        completed_stages=["s1"],
        all_stages=["s1", "s2"],
        prompts={"s1": "p1"},
        png_path=None,
    )
    d = s.to_dict()
    assert d["name"] == "alice"
    assert d["chapter"] == "2"
    assert d["progress"] == "1/2"
```

- [ ] **Step 4: Run test, verify failure**

Run: `uv run pytest tools/asset_dashboard/tests/test_manifest_io.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 5: Implement `manifest_io.py`**

```python
# tools/asset_dashboard/backend/manifest_io.py
"""Read manifest.json and project it as flat asset summaries for the dashboard."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Literal

AssetType = Literal["character", "tileset", "object"]

STAGE_ORDER: dict[AssetType, list[str]] = {
    "character": [
        "generate_8dir_base",
        "add_idle_animation",
        "add_walk_animation",
        "compile_spritesheet",
        "import_to_godot",
    ],
    "tileset": [
        "generate_atlas",
        "iso_project",
        "verify_in_godot",
        "import_to_godot",
    ],
    "object": [
        "generate_object",
        "chroma_key",
        "import_to_godot",
    ],
}


@dataclass
class AssetSummary:
    name: str
    asset_type: AssetType
    description: str | None
    tags: list[str]
    zone: str | None
    category: str | None
    chapter: str | None
    completed_stages: list[str]
    all_stages: list[str]
    prompts: dict[str, str]
    png_path: str | None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["progress"] = f"{len(self.completed_stages)}/{len(self.all_stages)}"
        return d


_BUCKETS: dict[str, AssetType] = {
    "characters": "character",
    "tilesets": "tileset",
    "objects": "object",
}


def _parse_tag(tags: list[str], key: str) -> str | None:
    prefix = f"{key}:"
    for t in tags:
        if t.startswith(prefix):
            return t[len(prefix):]
    return None


def load_assets(manifest_path: Path) -> list[AssetSummary]:
    if not manifest_path.exists():
        return []
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    out: list[AssetSummary] = []
    for bucket, asset_type in _BUCKETS.items():
        section = raw.get(bucket) or {}
        for name, entry in section.items():
            tags = list(entry.get("tags") or [])
            stages = entry.get("stages") or {}
            completed: list[str] = list(stages.keys())
            all_stages = STAGE_ORDER[asset_type]
            png_path = entry.get("game_png_path") or entry.get("local_path")
            out.append(AssetSummary(
                name=name,
                asset_type=asset_type,
                description=entry.get("description"),
                tags=tags,
                zone=_parse_tag(tags, "zone"),
                category=_parse_tag(tags, "category"),
                chapter=_parse_tag(tags, "chapter"),
                completed_stages=completed,
                all_stages=all_stages,
                prompts=dict(entry.get("prompts") or {}),
                png_path=png_path,
                extra={
                    "character_id": entry.get("character_id"),
                    "directions": entry.get("directions"),
                    "kind": entry.get("kind"),
                },
            ))
    return out
```

- [ ] **Step 6: Run test, verify pass**

Run: `uv run pytest tools/asset_dashboard/tests/test_manifest_io.py -v`
Expected: 3 passed.

- [ ] **Step 7: Write failing test for FastAPI server**

```python
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
```

- [ ] **Step 8: Run test, verify failure**

Run: `uv run pytest tools/asset_dashboard/tests/test_server.py -v`
Expected: FAIL — module `server` doesn't exist or app missing.

- [ ] **Step 9: Implement `server.py`**

```python
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
```

- [ ] **Step 10: Run all backend tests, verify pass**

Run: `uv run pytest tools/asset_dashboard/tests/ -v`
Expected: 6 passed total (3 manifest_io + 3 server).

- [ ] **Step 11: Commit**

```bash
git add tools/asset_dashboard/ pyproject.toml uv.lock
git commit -m "feat(dashboard): backend skeleton with manifest read endpoint"
```

---

## Task 4: Backend — thumbnail + prompt PATCH endpoints

**Files:**
- Create: `tools/asset_dashboard/backend/thumbnails.py`
- Create: `tools/asset_dashboard/tests/test_thumbnails.py`
- Modify: `tools/asset_dashboard/backend/server.py`
- Modify: `tools/asset_dashboard/tests/test_server.py`

- [ ] **Step 1: Write failing test for thumbnail picker**

```python
# tools/asset_dashboard/tests/test_thumbnails.py
from pathlib import Path

from tools.asset_dashboard.backend.thumbnails import resolve_thumbnail


def test_resolve_thumbnail_character_uses_south_rotation(tmp_path):
    char_dir = tmp_path / "art_source/pipeline/output/characters/alice"
    rot = char_dir / "rotations"
    rot.mkdir(parents=True)
    south = rot / "south.png"
    south.write_bytes(b"\x89PNG fake")
    result = resolve_thumbnail(tmp_path, "character", "alice", entry={})
    assert result == south


def test_resolve_thumbnail_object_uses_object_png(tmp_path):
    obj_dir = tmp_path / "art_source/pipeline/output/objects/lantern"
    obj_dir.mkdir(parents=True)
    png = obj_dir / "lantern.png"
    png.write_bytes(b"\x89PNG fake")
    result = resolve_thumbnail(tmp_path, "object", "lantern", entry={})
    assert result == png


def test_resolve_thumbnail_tileset_uses_iso_png(tmp_path):
    tileset_dir = tmp_path / "art_source/pipeline/output/tilesets/grass_dirt"
    tileset_dir.mkdir(parents=True)
    png = tileset_dir / "grass_dirt_iso.png"
    png.write_bytes(b"\x89PNG fake")
    result = resolve_thumbnail(tmp_path, "tileset", "grass_dirt", entry={})
    assert result == png


def test_resolve_thumbnail_returns_none_when_missing(tmp_path):
    result = resolve_thumbnail(tmp_path, "character", "ghost", entry={})
    assert result is None
```

- [ ] **Step 2: Run test, verify failure**

Run: `uv run pytest tools/asset_dashboard/tests/test_thumbnails.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `thumbnails.py`**

```python
# tools/asset_dashboard/backend/thumbnails.py
"""Pick a representative PNG to show as the asset thumbnail."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

AssetType = Literal["character", "tileset", "object"]


def resolve_thumbnail(
    repo_root: Path,
    asset_type: AssetType,
    name: str,
    entry: dict,
) -> Path | None:
    """Return the absolute path of a PNG to display as thumbnail, or None.

    Lookup rules:
      - character: <output>/characters/<name>/rotations/south.png
      - tileset:   <output>/tilesets/<name>/<name>_iso.png
      - object:    <output>/objects/<name>/<name>.png
    """
    pipeline_out = repo_root / "art_source" / "pipeline" / "output"
    if asset_type == "character":
        candidate = pipeline_out / "characters" / name / "rotations" / "south.png"
    elif asset_type == "tileset":
        candidate = pipeline_out / "tilesets" / name / f"{name}_iso.png"
    elif asset_type == "object":
        candidate = pipeline_out / "objects" / name / f"{name}.png"
    else:
        return None
    return candidate if candidate.exists() else None
```

- [ ] **Step 4: Run test, verify pass**

Run: `uv run pytest tools/asset_dashboard/tests/test_thumbnails.py -v`
Expected: 4 passed.

- [ ] **Step 5: Add prompt PATCH route + thumbnail route to server**

Append to `tools/asset_dashboard/backend/server.py` after the existing `manifest` function:

```python
import sys
from typing import Optional

from fastapi import HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .thumbnails import resolve_thumbnail

# Make `manifest` (the pipeline module) importable in this process for prompt edits.
sys.path.insert(0, str(REPO_ROOT / "art_source" / "pipeline"))
import manifest as pipeline_manifest  # noqa: E402


class PromptUpdate(BaseModel):
    stage: str
    prompt: str


@app.get("/api/asset/{asset_type}/{name}/thumbnail")
def thumbnail(asset_type: str, name: str) -> FileResponse:
    if asset_type not in ("character", "tileset", "object"):
        raise HTTPException(400, "invalid asset_type")
    png = resolve_thumbnail(REPO_ROOT, asset_type, name, entry={})
    if png is None:
        raise HTTPException(404, "no thumbnail available")
    return FileResponse(png, media_type="image/png")


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
```

- [ ] **Step 6: Append tests for new routes**

Append to `tools/asset_dashboard/tests/test_server.py`:

```python
def test_thumbnail_404_when_missing(client):
    r = client.get("/api/asset/character/alice/thumbnail")
    assert r.status_code == 404


def test_patch_prompt_for_unrealized_stage(client, tmp_path, monkeypatch):
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
```

The existing `client` fixture sets `server.MANIFEST_PATH`, but `pipeline_manifest` writes to its own `MANIFEST_PATH` constant. Patch it inside the fixture too — modify the existing `client` fixture in `test_server.py`:

Replace:
```python
    monkeypatch.setattr(server, "MANIFEST_PATH", mpath)
    return TestClient(server.app)
```

With:
```python
    monkeypatch.setattr(server, "MANIFEST_PATH", mpath)
    monkeypatch.setattr(server.pipeline_manifest, "MANIFEST_PATH", mpath)
    return TestClient(server.app)
```

- [ ] **Step 7: Run all tests, verify pass**

Run: `uv run pytest tools/asset_dashboard/tests/ -v`
Expected: 10 passed.

- [ ] **Step 8: Commit**

```bash
git add tools/asset_dashboard/
git commit -m "feat(dashboard): thumbnail + prompt PATCH endpoints with completion guard"
```

---

## Task 5: Backend — job runner (subprocess) + Remake endpoint

**Files:**
- Create: `tools/asset_dashboard/backend/jobs.py`
- Create: `tools/asset_dashboard/tests/test_jobs.py`
- Modify: `tools/asset_dashboard/backend/server.py`

`jobs.py` 管理 in-memory job 表。每個 job 是一個 subprocess.Popen。前端 poll job 狀態 + tail log。

- [ ] **Step 1: Write failing test for `JobRegistry`**

```python
# tools/asset_dashboard/tests/test_jobs.py
import sys
import time

import pytest

from tools.asset_dashboard.backend.jobs import JobRegistry, JobStatus


@pytest.fixture
def registry():
    return JobRegistry()


def test_start_records_running_job(registry):
    job_id = registry.start([sys.executable, "-c", "import time; time.sleep(0.5)"])
    info = registry.get(job_id)
    assert info is not None
    assert info.status in (JobStatus.RUNNING, JobStatus.COMPLETED)
    registry.wait(job_id, timeout=5)


def test_completed_job_has_zero_exit(registry):
    job_id = registry.start([sys.executable, "-c", "print('hi')"])
    registry.wait(job_id, timeout=5)
    info = registry.get(job_id)
    assert info.status == JobStatus.COMPLETED
    assert info.exit_code == 0
    assert "hi" in info.tail()


def test_failed_job_records_nonzero_exit(registry):
    job_id = registry.start([sys.executable, "-c", "import sys; sys.exit(2)"])
    registry.wait(job_id, timeout=5)
    info = registry.get(job_id)
    assert info.status == JobStatus.FAILED
    assert info.exit_code == 2


def test_list_jobs_returns_all(registry):
    j1 = registry.start([sys.executable, "-c", "pass"])
    j2 = registry.start([sys.executable, "-c", "pass"])
    registry.wait(j1, timeout=5)
    registry.wait(j2, timeout=5)
    ids = {j.id for j in registry.list()}
    assert ids == {j1, j2}


def test_tail_returns_last_n_lines(registry):
    code = "for i in range(20): print(f'line{i}')"
    job_id = registry.start([sys.executable, "-c", code])
    registry.wait(job_id, timeout=5)
    info = registry.get(job_id)
    last = info.tail(n=5).splitlines()
    assert last == ["line15", "line16", "line17", "line18", "line19"]
```

- [ ] **Step 2: Run test, verify failure**

Run: `uv run pytest tools/asset_dashboard/tests/test_jobs.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `jobs.py`**

```python
# tools/asset_dashboard/backend/jobs.py
"""In-memory job registry. Each job is a subprocess; output captured to a tempfile."""
from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobInfo:
    id: str
    cmd: list[str]
    cwd: Path
    log_path: Path
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    exit_code: int | None = None
    status: JobStatus = JobStatus.PENDING
    asset_name: str | None = None
    stage: str | None = None
    _process: subprocess.Popen | None = None

    def tail(self, n: int = 50) -> str:
        if not self.log_path.exists():
            return ""
        text = self.log_path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        return "\n".join(lines[-n:]) if len(lines) > n else text

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "cmd": self.cmd,
            "asset_name": self.asset_name,
            "stage": self.stage,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, JobInfo] = {}
        self._lock = threading.Lock()

    def start(
        self,
        cmd: list[str],
        cwd: Path | None = None,
        asset_name: str | None = None,
        stage: str | None = None,
    ) -> str:
        job_id = uuid.uuid4().hex[:12]
        log_path = Path(tempfile.gettempdir()) / f"muzha_dashboard_{job_id}.log"
        log_path.write_text("", encoding="utf-8")
        info = JobInfo(
            id=job_id,
            cmd=list(cmd),
            cwd=cwd or Path.cwd(),
            log_path=log_path,
            status=JobStatus.RUNNING,
            asset_name=asset_name,
            stage=stage,
        )
        log_fh = log_path.open("ab", buffering=0)
        proc = subprocess.Popen(
            cmd,
            cwd=str(info.cwd),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
        )
        info._process = proc
        with self._lock:
            self._jobs[job_id] = info

        threading.Thread(
            target=self._reaper, args=(job_id, log_fh), daemon=True
        ).start()
        return job_id

    def _reaper(self, job_id: str, log_fh) -> None:
        info = self._jobs[job_id]
        assert info._process is not None
        rc = info._process.wait()
        log_fh.close()
        info.finished_at = time.time()
        info.exit_code = rc
        info.status = JobStatus.COMPLETED if rc == 0 else JobStatus.FAILED

    def get(self, job_id: str) -> JobInfo | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[JobInfo]:
        with self._lock:
            return list(self._jobs.values())

    def wait(self, job_id: str, timeout: float = 30) -> None:
        info = self._jobs[job_id]
        deadline = time.time() + timeout
        while time.time() < deadline:
            if info.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                return
            time.sleep(0.05)
        raise TimeoutError(f"job {job_id} did not finish in {timeout}s")
```

- [ ] **Step 4: Run test, verify pass**

Run: `uv run pytest tools/asset_dashboard/tests/test_jobs.py -v`
Expected: 5 passed.

- [ ] **Step 5: Add Remake + jobs routes to server.py**

Append to `tools/asset_dashboard/backend/server.py`:

```python
from .jobs import JobRegistry, JobStatus

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
```

- [ ] **Step 6: Add server-level test for /api/jobs**

Append to `tools/asset_dashboard/tests/test_server.py`:

```python
def test_list_jobs_initially_empty(client):
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert r.json() == {"jobs": []}


def test_job_detail_404_for_missing(client):
    r = client.get("/api/jobs/nope")
    assert r.status_code == 404
```

- [ ] **Step 7: Run full test suite, verify pass**

Run: `uv run pytest tools/asset_dashboard/tests/ -v`
Expected: 17 passed.

- [ ] **Step 8: Commit**

```bash
git add tools/asset_dashboard/
git commit -m "feat(dashboard): job registry + remake endpoint triggers orchestrator subprocess"
```

---

## Task 6: Frontend scaffold (Vite + React + TS + Tailwind)

**Files:**
- Create: `tools/asset_dashboard/frontend/package.json`
- Create: `tools/asset_dashboard/frontend/tsconfig.json`
- Create: `tools/asset_dashboard/frontend/tsconfig.node.json`
- Create: `tools/asset_dashboard/frontend/vite.config.ts`
- Create: `tools/asset_dashboard/frontend/tailwind.config.js`
- Create: `tools/asset_dashboard/frontend/postcss.config.js`
- Create: `tools/asset_dashboard/frontend/index.html`
- Create: `tools/asset_dashboard/frontend/src/main.tsx`
- Create: `tools/asset_dashboard/frontend/src/App.tsx`
- Create: `tools/asset_dashboard/frontend/src/index.css`
- Create: `tools/asset_dashboard/frontend/.gitignore`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "muzharpg-asset-dashboard",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "lucide-react": "^0.460.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.16",
    "typescript": "^5.7.2",
    "vite": "^6.0.3"
  }
}
```

- [ ] **Step 2: Create `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 3: Create `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4: Create `frontend/vite.config.ts`**

```typescript
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8765",
    },
  },
  build: {
    outDir: "dist",
  },
})
```

- [ ] **Step 5: Create `frontend/tailwind.config.js`**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

- [ ] **Step 6: Create `frontend/postcss.config.js`**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 7: Create `frontend/index.html`**

```html
<!doctype html>
<html lang="zh-Hant">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MuzhaRPG Asset Dashboard</title>
  </head>
  <body class="bg-stone-950 text-stone-100">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 8: Create `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html, body, #root {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang TC",
               "Microsoft JhengHei", sans-serif;
}
```

- [ ] **Step 9: Create `frontend/src/main.tsx`**

```tsx
import React from "react"
import ReactDOM from "react-dom/client"
import App from "./App.tsx"
import "./index.css"

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

- [ ] **Step 10: Create `frontend/src/App.tsx` (placeholder)**

```tsx
export default function App() {
  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-2">MuzhaRPG Asset Dashboard</h1>
      <p className="text-stone-400">Loading…</p>
    </div>
  )
}
```

- [ ] **Step 11: Create `frontend/.gitignore`**

```
node_modules
dist
.vite
```

- [ ] **Step 12: Install + verify build**

Run from `tools/asset_dashboard/frontend/`:
```powershell
cd tools/asset_dashboard/frontend
pnpm install
pnpm build
cd ../../..
```
Expected: `dist/` directory created with index.html + assets, no TypeScript errors.

- [ ] **Step 13: Commit**

```bash
git add tools/asset_dashboard/frontend/
git commit -m "feat(dashboard): frontend scaffold (Vite + React + TS + Tailwind)"
```

---

## Task 7: Frontend — types, api client, App fetches manifest

**Files:**
- Create: `tools/asset_dashboard/frontend/src/types.ts`
- Create: `tools/asset_dashboard/frontend/src/api.ts`
- Modify: `tools/asset_dashboard/frontend/src/App.tsx`

- [ ] **Step 1: Create `src/types.ts`**

```typescript
export type AssetType = "character" | "tileset" | "object"

export interface AssetSummary {
  name: string
  asset_type: AssetType
  description: string | null
  tags: string[]
  zone: string | null
  category: string | null
  chapter: string | null
  completed_stages: string[]
  all_stages: string[]
  prompts: Record<string, string>
  png_path: string | null
  progress: string
  extra: Record<string, unknown>
}

export interface ManifestResponse {
  assets: AssetSummary[]
  manifest_path: string
}

export interface JobInfo {
  id: string
  cmd: string[]
  asset_name: string | null
  stage: string | null
  status: "pending" | "running" | "completed" | "failed"
  exit_code: number | null
  started_at: number
  finished_at: number | null
  tail?: string
}
```

- [ ] **Step 2: Create `src/api.ts`**

```typescript
import type { AssetType, JobInfo, ManifestResponse } from "./types"

const BASE = ""

async function jsonFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(BASE + url, init)
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`)
  return r.json() as Promise<T>
}

export const api = {
  manifest(): Promise<ManifestResponse> {
    return jsonFetch<ManifestResponse>("/api/manifest")
  },

  thumbnailUrl(assetType: AssetType, name: string): string {
    return `${BASE}/api/asset/${assetType}/${encodeURIComponent(name)}/thumbnail`
  },

  async patchPrompt(
    assetType: AssetType,
    name: string,
    stage: string,
    prompt: string
  ): Promise<void> {
    await jsonFetch(`/api/asset/${assetType}/${encodeURIComponent(name)}/prompts`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage, prompt }),
    })
  },

  async remake(
    assetType: AssetType,
    name: string,
    stage: string,
    prompt?: string
  ): Promise<{ job_id: string; stage: string }> {
    return jsonFetch(`/api/asset/${assetType}/${encodeURIComponent(name)}/remake`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ stage, prompt }),
    })
  },

  jobs(): Promise<{ jobs: JobInfo[] }> {
    return jsonFetch("/api/jobs")
  },

  jobDetail(jobId: string): Promise<JobInfo> {
    return jsonFetch(`/api/jobs/${jobId}`)
  },
}
```

- [ ] **Step 3: Replace `src/App.tsx` with manifest-loading shell**

```tsx
import { useEffect, useState } from "react"
import type { AssetSummary } from "./types"
import { api } from "./api"

export default function App() {
  const [assets, setAssets] = useState<AssetSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let stopped = false
    const tick = async () => {
      try {
        const data = await api.manifest()
        if (!stopped) {
          setAssets(data.assets)
          setError(null)
        }
      } catch (e) {
        if (!stopped) setError((e as Error).message)
      } finally {
        if (!stopped) setLoading(false)
      }
    }
    tick()
    const id = setInterval(tick, 2000)
    return () => {
      stopped = true
      clearInterval(id)
    }
  }, [])

  return (
    <div className="min-h-screen p-6">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Asset Dashboard</h1>
        <span className="text-sm text-stone-400">{assets.length} assets</span>
      </header>
      {error && (
        <div className="mb-4 rounded bg-red-900/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}
      {loading ? (
        <p className="text-stone-400">Loading…</p>
      ) : (
        <pre className="rounded bg-stone-900 p-4 text-xs text-stone-300">
          {JSON.stringify(assets.slice(0, 3), null, 2)}
        </pre>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Build to verify TS types**

Run: `cd tools/asset_dashboard/frontend && pnpm build && cd ../../..`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add tools/asset_dashboard/frontend/src/types.ts tools/asset_dashboard/frontend/src/api.ts tools/asset_dashboard/frontend/src/App.tsx
git commit -m "feat(dashboard): frontend types, api client, polling shell"
```

---

## Task 8: Frontend — FilterBar component

**Files:**
- Create: `tools/asset_dashboard/frontend/src/components/FilterBar.tsx`
- Modify: `tools/asset_dashboard/frontend/src/App.tsx`

- [ ] **Step 1: Create `src/components/FilterBar.tsx`**

```tsx
import type { AssetSummary, AssetType } from "../types"

export interface FilterState {
  search: string
  assetType: AssetType | "all"
  chapter: string | "all"
  status: "all" | "in_progress" | "complete"
}

export function makeInitialFilter(): FilterState {
  return { search: "", assetType: "all", chapter: "all", status: "all" }
}

interface Props {
  filter: FilterState
  onChange: (f: FilterState) => void
  assets: AssetSummary[]
}

export function FilterBar({ filter, onChange, assets }: Props) {
  const chapters = Array.from(
    new Set(assets.map((a) => a.chapter).filter((c): c is string => c !== null))
  ).sort()

  return (
    <div className="mb-6 flex flex-wrap gap-3">
      <input
        type="text"
        placeholder="Search by name or description…"
        className="rounded bg-stone-800 px-3 py-2 text-sm placeholder:text-stone-500 focus:outline-none focus:ring-1 focus:ring-stone-500"
        value={filter.search}
        onChange={(e) => onChange({ ...filter, search: e.target.value })}
      />
      <select
        className="rounded bg-stone-800 px-3 py-2 text-sm"
        value={filter.assetType}
        onChange={(e) =>
          onChange({ ...filter, assetType: e.target.value as FilterState["assetType"] })
        }
      >
        <option value="all">All types</option>
        <option value="character">Characters</option>
        <option value="object">Props / Buildings</option>
        <option value="tileset">Tilesets</option>
      </select>
      <select
        className="rounded bg-stone-800 px-3 py-2 text-sm"
        value={filter.chapter}
        onChange={(e) => onChange({ ...filter, chapter: e.target.value })}
      >
        <option value="all">All chapters</option>
        {chapters.map((c) => (
          <option key={c} value={c}>
            Chapter {c}
          </option>
        ))}
      </select>
      <select
        className="rounded bg-stone-800 px-3 py-2 text-sm"
        value={filter.status}
        onChange={(e) =>
          onChange({ ...filter, status: e.target.value as FilterState["status"] })
        }
      >
        <option value="all">Any status</option>
        <option value="in_progress">In progress</option>
        <option value="complete">Complete</option>
      </select>
    </div>
  )
}

export function applyFilter(assets: AssetSummary[], filter: FilterState): AssetSummary[] {
  return assets.filter((a) => {
    if (filter.assetType !== "all" && a.asset_type !== filter.assetType) return false
    if (filter.chapter !== "all" && a.chapter !== filter.chapter) return false
    if (filter.status === "in_progress" && a.completed_stages.length === a.all_stages.length)
      return false
    if (filter.status === "complete" && a.completed_stages.length !== a.all_stages.length)
      return false
    if (filter.search.trim()) {
      const needle = filter.search.toLowerCase()
      const hay = (a.name + " " + (a.description ?? "")).toLowerCase()
      if (!hay.includes(needle)) return false
    }
    return true
  })
}
```

- [ ] **Step 2: Wire FilterBar into App.tsx**

Replace `src/App.tsx` with:

```tsx
import { useEffect, useState } from "react"
import type { AssetSummary } from "./types"
import { api } from "./api"
import { FilterBar, applyFilter, makeInitialFilter } from "./components/FilterBar"

export default function App() {
  const [assets, setAssets] = useState<AssetSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState(makeInitialFilter())

  useEffect(() => {
    let stopped = false
    const tick = async () => {
      try {
        const data = await api.manifest()
        if (!stopped) {
          setAssets(data.assets)
          setError(null)
        }
      } catch (e) {
        if (!stopped) setError((e as Error).message)
      } finally {
        if (!stopped) setLoading(false)
      }
    }
    tick()
    const id = setInterval(tick, 2000)
    return () => {
      stopped = true
      clearInterval(id)
    }
  }, [])

  const visible = applyFilter(assets, filter)

  return (
    <div className="min-h-screen p-6">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Asset Dashboard</h1>
        <span className="text-sm text-stone-400">
          {visible.length} of {assets.length} assets
        </span>
      </header>
      {error && (
        <div className="mb-4 rounded bg-red-900/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}
      <FilterBar filter={filter} onChange={setFilter} assets={assets} />
      {loading ? (
        <p className="text-stone-400">Loading…</p>
      ) : (
        <pre className="rounded bg-stone-900 p-4 text-xs text-stone-300">
          {JSON.stringify(visible.slice(0, 3), null, 2)}
        </pre>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Build to verify**

Run: `cd tools/asset_dashboard/frontend && pnpm build && cd ../../..`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add tools/asset_dashboard/frontend/src/
git commit -m "feat(dashboard): FilterBar (search/type/chapter/status)"
```

---

## Task 9: Frontend — AssetCard with thumbnail + stage progress

**Files:**
- Create: `tools/asset_dashboard/frontend/src/components/AssetCard.tsx`
- Create: `tools/asset_dashboard/frontend/src/components/StageList.tsx`
- Create: `tools/asset_dashboard/frontend/src/components/AssetGrid.tsx`
- Modify: `tools/asset_dashboard/frontend/src/App.tsx`

- [ ] **Step 1: Create `src/components/StageList.tsx`**

```tsx
import { Check, Circle } from "lucide-react"
import type { AssetSummary } from "../types"

interface Props {
  asset: AssetSummary
}

export function StageList({ asset }: Props) {
  const completed = new Set(asset.completed_stages)
  return (
    <ol className="space-y-1 text-sm">
      {asset.all_stages.map((stage) => {
        const done = completed.has(stage)
        return (
          <li key={stage} className="flex items-center gap-2">
            {done ? (
              <Check className="h-4 w-4 text-emerald-400" />
            ) : (
              <Circle className="h-4 w-4 text-stone-600" />
            )}
            <span className={done ? "text-stone-200" : "text-stone-500"}>
              {stage}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
```

- [ ] **Step 2: Create `src/components/AssetCard.tsx`**

```tsx
import { useState } from "react"
import { ImageOff } from "lucide-react"
import type { AssetSummary } from "../types"
import { api } from "../api"
import { StageList } from "./StageList"

interface Props {
  asset: AssetSummary
}

export function AssetCard({ asset }: Props) {
  const [thumbBroken, setThumbBroken] = useState(false)
  const thumbUrl = api.thumbnailUrl(asset.asset_type, asset.name)

  return (
    <div className="rounded-lg border border-stone-800 bg-stone-900 p-4">
      <div className="mb-3 flex h-32 items-center justify-center overflow-hidden rounded bg-stone-950">
        {thumbBroken ? (
          <ImageOff className="h-10 w-10 text-stone-700" />
        ) : (
          <img
            src={thumbUrl}
            alt={asset.name}
            className="max-h-full max-w-full object-contain"
            onError={() => setThumbBroken(true)}
            style={{ imageRendering: "pixelated" }}
          />
        )}
      </div>
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h3 className="truncate font-mono text-sm font-semibold">{asset.name}</h3>
        <span className="text-xs text-stone-500">{asset.progress}</span>
      </div>
      <div className="mb-3 flex flex-wrap gap-1">
        {asset.tags.map((t) => (
          <span
            key={t}
            className="rounded bg-stone-800 px-2 py-0.5 text-[10px] text-stone-400"
          >
            {t}
          </span>
        ))}
      </div>
      <StageList asset={asset} />
    </div>
  )
}
```

- [ ] **Step 3: Create `src/components/AssetGrid.tsx`**

```tsx
import type { AssetSummary } from "../types"
import { AssetCard } from "./AssetCard"

interface Props {
  assets: AssetSummary[]
}

export function AssetGrid({ assets }: Props) {
  if (assets.length === 0) {
    return <p className="text-stone-500">No assets match these filters.</p>
  }
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {assets.map((a) => (
        <AssetCard key={`${a.asset_type}:${a.name}`} asset={a} />
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Wire into App.tsx**

Replace the `<pre>...</pre>` block in `src/App.tsx` with `<AssetGrid assets={visible} />`. Add the import:

```tsx
import { AssetGrid } from "./components/AssetGrid"
```

The full updated file:

```tsx
import { useEffect, useState } from "react"
import type { AssetSummary } from "./types"
import { api } from "./api"
import { FilterBar, applyFilter, makeInitialFilter } from "./components/FilterBar"
import { AssetGrid } from "./components/AssetGrid"

export default function App() {
  const [assets, setAssets] = useState<AssetSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState(makeInitialFilter())

  useEffect(() => {
    let stopped = false
    const tick = async () => {
      try {
        const data = await api.manifest()
        if (!stopped) {
          setAssets(data.assets)
          setError(null)
        }
      } catch (e) {
        if (!stopped) setError((e as Error).message)
      } finally {
        if (!stopped) setLoading(false)
      }
    }
    tick()
    const id = setInterval(tick, 2000)
    return () => {
      stopped = true
      clearInterval(id)
    }
  }, [])

  const visible = applyFilter(assets, filter)

  return (
    <div className="min-h-screen p-6">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Asset Dashboard</h1>
        <span className="text-sm text-stone-400">
          {visible.length} of {assets.length} assets
        </span>
      </header>
      {error && (
        <div className="mb-4 rounded bg-red-900/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}
      <FilterBar filter={filter} onChange={setFilter} assets={assets} />
      {loading ? <p className="text-stone-400">Loading…</p> : <AssetGrid assets={visible} />}
    </div>
  )
}
```

- [ ] **Step 5: Build**

Run: `cd tools/asset_dashboard/frontend && pnpm build && cd ../../..`
Expected: build succeeds.

- [ ] **Step 6: Commit**

```bash
git add tools/asset_dashboard/frontend/src/
git commit -m "feat(dashboard): AssetGrid + AssetCard with thumbnails and stage progress"
```

---

## Task 10: Frontend — PromptEditor (rocked / unlocked / Remake flow)

**Files:**
- Create: `tools/asset_dashboard/frontend/src/components/PromptEditor.tsx`
- Modify: `tools/asset_dashboard/frontend/src/components/AssetCard.tsx`

- [ ] **Step 1: Create `src/components/PromptEditor.tsx`**

```tsx
import { useState } from "react"
import { Lock, Unlock, Send, RotateCcw } from "lucide-react"
import type { AssetSummary } from "../types"
import { api } from "../api"

interface Props {
  asset: AssetSummary
  stage: string
  initialPrompt: string
  realized: boolean
}

export function PromptEditor({ asset, stage, initialPrompt, realized }: Props) {
  const [text, setText] = useState(initialPrompt)
  const [unlocked, setUnlocked] = useState(!realized)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const onSubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      if (realized && unlocked) {
        await api.remake(asset.asset_type, asset.name, stage, text)
      } else {
        await api.patchPrompt(asset.asset_type, asset.name, stage, text)
      }
      setUnlocked(false)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const onRemake = () => {
    if (window.confirm(`Remake stage "${stage}"? 此 stage 之後的下游 stage 不會自動失效,需要分別 remake。`)) {
      setUnlocked(true)
    }
  }

  const editable = unlocked && !submitting

  return (
    <div className="mt-2 rounded border border-stone-800 bg-stone-950 p-2">
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="font-mono text-stone-400">{stage}</span>
        {realized && !unlocked && (
          <span className="flex items-center gap-1 text-stone-600">
            <Lock className="h-3 w-3" /> realized
          </span>
        )}
        {unlocked && (
          <span className="flex items-center gap-1 text-amber-400">
            <Unlock className="h-3 w-3" /> editable
          </span>
        )}
      </div>
      <textarea
        className={`w-full rounded px-2 py-1 text-xs font-mono leading-relaxed
          ${editable ? "bg-stone-800 text-stone-100" : "bg-stone-900 text-stone-500"}`}
        rows={2}
        value={text}
        readOnly={!editable}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="mt-1 flex items-center gap-2">
        {realized && !unlocked && (
          <button
            type="button"
            onClick={onRemake}
            className="flex items-center gap-1 rounded bg-stone-800 px-2 py-1 text-xs hover:bg-stone-700"
          >
            <RotateCcw className="h-3 w-3" />
            Remake
          </button>
        )}
        {editable && (
          <button
            type="button"
            disabled={submitting || text === initialPrompt}
            onClick={onSubmit}
            className="flex items-center gap-1 rounded bg-emerald-700 px-2 py-1 text-xs text-emerald-50 disabled:bg-stone-700 disabled:text-stone-500"
          >
            <Send className="h-3 w-3" />
            {submitting ? "Submitting…" : realized ? "Remake & Submit" : "Submit"}
          </button>
        )}
        {error && <span className="text-xs text-red-400">{error}</span>}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add prompt section to AssetCard**

Replace the contents of `src/components/AssetCard.tsx` with:

```tsx
import { useState } from "react"
import { ImageOff } from "lucide-react"
import type { AssetSummary } from "../types"
import { api } from "../api"
import { StageList } from "./StageList"
import { PromptEditor } from "./PromptEditor"

interface Props {
  asset: AssetSummary
}

export function AssetCard({ asset }: Props) {
  const [thumbBroken, setThumbBroken] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const thumbUrl = api.thumbnailUrl(asset.asset_type, asset.name)

  const completed = new Set(asset.completed_stages)

  return (
    <div className="rounded-lg border border-stone-800 bg-stone-900 p-4">
      <div className="mb-3 flex h-32 items-center justify-center overflow-hidden rounded bg-stone-950">
        {thumbBroken ? (
          <ImageOff className="h-10 w-10 text-stone-700" />
        ) : (
          <img
            src={thumbUrl}
            alt={asset.name}
            className="max-h-full max-w-full object-contain"
            onError={() => setThumbBroken(true)}
            style={{ imageRendering: "pixelated" }}
          />
        )}
      </div>
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <h3 className="truncate font-mono text-sm font-semibold">{asset.name}</h3>
        <span className="text-xs text-stone-500">{asset.progress}</span>
      </div>
      <div className="mb-3 flex flex-wrap gap-1">
        {asset.tags.map((t) => (
          <span
            key={t}
            className="rounded bg-stone-800 px-2 py-0.5 text-[10px] text-stone-400"
          >
            {t}
          </span>
        ))}
      </div>
      <StageList asset={asset} />
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="mt-3 text-xs text-stone-500 hover:text-stone-300"
      >
        {expanded ? "Hide prompts ▴" : "Show prompts ▾"}
      </button>
      {expanded && (
        <div className="mt-2">
          {asset.all_stages.map((stage) => {
            const realized = completed.has(stage)
            const initial =
              asset.prompts[stage] ??
              (stage.startsWith("generate_") ? asset.description ?? "" : "")
            return (
              <PromptEditor
                key={stage}
                asset={asset}
                stage={stage}
                initialPrompt={initial}
                realized={realized}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Build**

Run: `cd tools/asset_dashboard/frontend && pnpm build && cd ../../..`
Expected: build succeeds.

- [ ] **Step 4: Commit**

```bash
git add tools/asset_dashboard/frontend/src/components/
git commit -m "feat(dashboard): PromptEditor with realized/unlocked/Remake flow"
```

---

## Task 11: Frontend — JobLogPanel + serve frontend from FastAPI

**Files:**
- Create: `tools/asset_dashboard/frontend/src/components/JobLogPanel.tsx`
- Modify: `tools/asset_dashboard/frontend/src/App.tsx`
- Modify: `tools/asset_dashboard/backend/server.py`

- [ ] **Step 1: Create `src/components/JobLogPanel.tsx`**

```tsx
import { useEffect, useState } from "react"
import { Loader2, X } from "lucide-react"
import type { JobInfo } from "../types"
import { api } from "../api"

export function JobLogPanel() {
  const [jobs, setJobs] = useState<JobInfo[]>([])
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const [tail, setTail] = useState("")

  useEffect(() => {
    let stopped = false
    const tick = async () => {
      try {
        const r = await api.jobs()
        if (!stopped) setJobs(r.jobs)
      } catch {
        /* ignore transient errors */
      }
    }
    tick()
    const id = setInterval(tick, 2000)
    return () => {
      stopped = true
      clearInterval(id)
    }
  }, [])

  useEffect(() => {
    if (!selected) return
    let stopped = false
    const tick = async () => {
      try {
        const j = await api.jobDetail(selected)
        if (!stopped) setTail(j.tail ?? "")
      } catch {
        /* ignore */
      }
    }
    tick()
    const id = setInterval(tick, 1500)
    return () => {
      stopped = true
      clearInterval(id)
    }
  }, [selected])

  const running = jobs.filter((j) => j.status === "running").length

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-4 right-4 flex items-center gap-2 rounded-full bg-stone-800 px-4 py-2 text-sm shadow-lg hover:bg-stone-700"
      >
        {running > 0 && <Loader2 className="h-4 w-4 animate-spin text-amber-400" />}
        Jobs ({jobs.length})
      </button>
      {open && (
        <div className="fixed bottom-16 right-4 max-h-[70vh] w-96 overflow-hidden rounded-lg border border-stone-700 bg-stone-900 shadow-xl">
          <div className="flex items-center justify-between border-b border-stone-800 px-3 py-2">
            <span className="text-sm font-semibold">Jobs</span>
            <button onClick={() => setOpen(false)}>
              <X className="h-4 w-4" />
            </button>
          </div>
          <ul className="max-h-48 overflow-y-auto">
            {jobs.length === 0 && (
              <li className="px-3 py-2 text-xs text-stone-500">No jobs yet.</li>
            )}
            {jobs.map((j) => (
              <li
                key={j.id}
                className={`cursor-pointer border-b border-stone-800 px-3 py-2 text-xs hover:bg-stone-800
                  ${selected === j.id ? "bg-stone-800" : ""}`}
                onClick={() => setSelected(j.id)}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono">{j.asset_name ?? j.id}</span>
                  <span
                    className={
                      j.status === "running"
                        ? "text-amber-400"
                        : j.status === "completed"
                        ? "text-emerald-400"
                        : j.status === "failed"
                        ? "text-red-400"
                        : "text-stone-500"
                    }
                  >
                    {j.status}
                  </span>
                </div>
                <div className="text-[10px] text-stone-500">
                  {j.stage ?? "—"}
                </div>
              </li>
            ))}
          </ul>
          {selected && (
            <pre className="max-h-72 overflow-auto bg-stone-950 p-3 text-[10px] leading-snug text-stone-300">
              {tail || "(no output yet)"}
            </pre>
          )}
        </div>
      )}
    </>
  )
}
```

- [ ] **Step 2: Mount JobLogPanel in App.tsx**

Add the import + render. Replace the contents of `src/App.tsx` with:

```tsx
import { useEffect, useState } from "react"
import type { AssetSummary } from "./types"
import { api } from "./api"
import { FilterBar, applyFilter, makeInitialFilter } from "./components/FilterBar"
import { AssetGrid } from "./components/AssetGrid"
import { JobLogPanel } from "./components/JobLogPanel"

export default function App() {
  const [assets, setAssets] = useState<AssetSummary[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState(makeInitialFilter())

  useEffect(() => {
    let stopped = false
    const tick = async () => {
      try {
        const data = await api.manifest()
        if (!stopped) {
          setAssets(data.assets)
          setError(null)
        }
      } catch (e) {
        if (!stopped) setError((e as Error).message)
      } finally {
        if (!stopped) setLoading(false)
      }
    }
    tick()
    const id = setInterval(tick, 2000)
    return () => {
      stopped = true
      clearInterval(id)
    }
  }, [])

  const visible = applyFilter(assets, filter)

  return (
    <div className="min-h-screen p-6">
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Asset Dashboard</h1>
        <span className="text-sm text-stone-400">
          {visible.length} of {assets.length} assets
        </span>
      </header>
      {error && (
        <div className="mb-4 rounded bg-red-900/30 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}
      <FilterBar filter={filter} onChange={setFilter} assets={assets} />
      {loading ? <p className="text-stone-400">Loading…</p> : <AssetGrid assets={visible} />}
      <JobLogPanel />
    </div>
  )
}
```

- [ ] **Step 3: Mount built frontend in FastAPI**

Append to `tools/asset_dashboard/backend/server.py`:

```python
from fastapi.staticfiles import StaticFiles

_FRONTEND_DIST = REPO_ROOT / "tools" / "asset_dashboard" / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
```

This must be the LAST thing in server.py — `app.mount("/", ...)` is a catch-all and shadows nothing because /api/* routes are already registered when the file finishes executing.

- [ ] **Step 4: Build frontend**

Run: `cd tools/asset_dashboard/frontend && pnpm build && cd ../../..`
Expected: `dist/` populated.

- [ ] **Step 5: Smoke test full stack**

Run: `uv run uvicorn tools.asset_dashboard.backend.server:app --port 8765`
Open browser to `http://localhost:8765/` — should see the dashboard with at least the player asset card. `Ctrl+C` to stop.

- [ ] **Step 6: Run all tests**

Run: `uv run pytest tools/asset_dashboard/tests/ -v`
Expected: 17 passed.

- [ ] **Step 7: Commit**

```bash
git add tools/asset_dashboard/
git commit -m "feat(dashboard): JobLogPanel + serve built frontend from FastAPI"
```

---

## Task 12: README + skill / memory updates

**Files:**
- Create: `tools/asset_dashboard/README.md`
- Modify: `docs/INDEX.md`
- Modify: `.claude/skills/art-pipeline/SKILL.md`
- Memory: `<memory>/reference_asset_dashboard.md` + index entry

- [ ] **Step 1: Write `tools/asset_dashboard/README.md`**

```markdown
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

- Reads `art_source/pipeline/output/manifest.json`.
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
```

- [ ] **Step 2: Update `docs/INDEX.md`**

Find the section listing tools or scripts. Add:

```markdown
| `tools/asset_dashboard/` | 程式 / 美術 | 內部 Web UI:瀏覽 art-pipeline 產出 + 編輯 prompt + Remake |
```

(adjust position so it groups with other tooling rows; engineer should read the file first to find the right spot.)

- [ ] **Step 3: Add a one-liner to `.claude/skills/art-pipeline/SKILL.md`**

Locate the existing "Where to escalate" section near the bottom and append a bullet:

```markdown
- 視覺化檢視 + 編輯 prompt + Remake:啟動 `tools/asset_dashboard/`(`uv run uvicorn tools.asset_dashboard.backend.server:app --port 8765`),開 http://localhost:8765/。
```

- [ ] **Step 4: Write memory file**

Use the Write tool to create
`C:\Users\Justin\.claude\projects\c--Users-Justin-Documents-GitHub-MuzhaRPG-Project\memory\reference_asset_dashboard.md`:

```markdown
---
name: Asset Dashboard 位置與啟動
description: 美術組用的 Web UI 看 pipeline 進度、編輯 prompt、按 Remake 重生;tools/asset_dashboard/
type: reference
---
位置: `tools/asset_dashboard/`(backend FastAPI + frontend Vite/React/TS)。
啟動:
```
cd tools/asset_dashboard/frontend && pnpm install && pnpm build && cd ../../..
uv run uvicorn tools.asset_dashboard.backend.server:app --port 8765
```
然後開 http://localhost:8765。dev 模式 frontend hot reload 用 `pnpm dev`(port 5173,proxy /api 到 backend)。

**Why:** 取代靠 ai 看 manifest.json 的工作流。美術組可以視覺化看資產 stage 進度,直接編輯未實現 prompt,或 Remake 已實現的 stage 重新生成。

**How to apply:** 看到使用者要查看 pipeline 進度、編輯 prompt、視覺化資產時,可以建議他們開 dashboard。Manifest schema 新增 `prompts` 欄位記錄每個 stage 的 prompt(stage 1 fallback 到舊 `description`)。
```

Then update `MEMORY.md` (same dir) — add a new line near the existing art-pipeline entries:

```markdown
- [Asset Dashboard](reference_asset_dashboard.md) — Web UI (tools/asset_dashboard/) 看 pipeline 進度 + 編輯 prompt + Remake
```

- [ ] **Step 5: Commit**

```bash
git add tools/asset_dashboard/README.md docs/INDEX.md .claude/skills/art-pipeline/SKILL.md
git commit -m "docs: asset dashboard quickstart + skill / memory entries"
```

(Memory updates are outside the repo and not committed.)

---

## Self-Review

**Spec coverage:**
- Browse by chapter / type / folder structure → Task 8 (FilterBar) + Task 9 (AssetGrid) ✓
- Show stage progress → Task 9 (StageList) ✓
- Show current prompt + next-stage prompt → Task 10 (PromptEditor inside AssetCard expansion) ✓
- Editable for unrealized → Task 10 ✓
- Locked + Remake unlock for realized → Task 10 ✓
- Submit triggers regeneration → Task 5 (backend) + Task 10 (frontend) ✓
- Stack: TS + 極簡 CSS → Tailwind utility classes (Task 6) ✓
- Need separate prompt files? — answered NO, manifest schema extended (Task 1) ✓
- Lock state UI-only → Task 10 PromptEditor ✓
- Thumbnails → Task 4 (backend) + Task 9 (frontend) ✓

**Placeholder scan:** All "TBD" / "validation" / "error handling" wording is replaced with concrete code. Step 2 of Task 11 says "engineer should read the file first to find the right spot" — that's a guidance note for INDEX.md positioning, not a code placeholder, acceptable.

**Type consistency:**
- `AssetSummary` defined in Task 3 (Python dataclass) and Task 7 (TS interface) — fields match: name, asset_type, description, tags, zone, category, chapter, completed_stages, all_stages, prompts, png_path, progress (TS adds progress because backend computes it in to_dict).
- `JobInfo.to_dict` keys match `JobInfo` TS interface: id, cmd, asset_name, stage, status, exit_code, started_at, finished_at, tail.
- `RemakeRequest` (backend) ↔ `api.remake(stage, prompt)` payload (frontend).
- `PromptUpdate` (backend) ↔ `api.patchPrompt(stage, prompt)` payload (frontend).

All consistent.

## Out of scope

- Multi-asset bulk Remake.
- Direct asset deletion from UI.
- Manifest version migration UI (one-time migration was Task 1's lazy fallback).
- Authentication (single-user local tool).
- WebSocket push (polling is enough at 2s cadence).
