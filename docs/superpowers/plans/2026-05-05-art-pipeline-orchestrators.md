# Art Pipeline Orchestrators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `art_source/pipeline/` 擴成 4 條 CLI orchestrator(autotile / prop / npc_static / npc_moving),支援 stage-by-stage 暫停、resume、批次模式;最小化 MCP 層變更並清掉 v1 死碼。

**Architecture:** 在 `art_source/pipeline/` 下新增 `orchestrators/` 子目錄,以 `_common.py` 提供 `@stage` 裝飾器 + CLI 共用參數;manifest.json 加 `stages` 欄位記錄每階段狀態;MCP 層只動 `create_character` 加 `directions` 參數、新增 `create_iso_prop` 工具,並補對應 client wrapper。

**Tech Stack:** Python 3.13、pytest、Pillow、requests、python-dotenv、FastMCP。Pixellab v2 API。

**Spec:** [docs/superpowers/specs/2026-05-05-art-pipeline-orchestrators-design.md](../specs/2026-05-05-art-pipeline-orchestrators-design.md)

---

## File Structure

| 檔案 | 動作 | 責任 |
|---|---|---|
| `pyproject.toml` | Modify | 加 pytest 到 dev dep |
| `tests/__init__.py` | Create | 空 |
| `tests/test_manifest_stages.py` | Create | manifest stages CRUD |
| `tests/test_stage_framework.py` | Create | `@stage` 裝飾器、resume、review-mode |
| `tests/test_pixellab_client_wrappers.py` | Create | submit_character_4dir / submit_iso_tile 參數驗證(不打 API) |
| `art_source/pipeline/manifest.py` | Modify | 加 `mark_stage` / `get_completed_stages` |
| `art_source/pipeline/pixellab_client.py` | Modify | 刪 v1 死碼;加 `submit_character_4dir`、`submit_iso_tile` |
| `art_source/pipeline/mcp_server.py` | Modify | `create_character` 加 `directions` 參數;新增 `create_iso_prop` |
| `art_source/pipeline/orchestrators/__init__.py` | Create | 空 |
| `art_source/pipeline/orchestrators/_common.py` | Create | stage 框架 + CLI 解析 + StageContext |
| `art_source/pipeline/orchestrators/autotile.py` | Create | Pipeline 1 |
| `art_source/pipeline/orchestrators/prop.py` | Create | Pipeline 2(`--kind=building|iso_prop`) |
| `art_source/pipeline/orchestrators/npc_static.py` | Create | Pipeline 3 |
| `art_source/pipeline/orchestrators/npc_moving.py` | Create | Pipeline 4 |
| `art_source/pipeline/README.md` | Modify | 加 orchestrators 區塊 |
| `docs/INDEX.md` | Modify | 加 orchestrator 條目 |

---

## Task 1: Test Infrastructure

**Files:**
- Modify: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Add pytest to dev dependencies**

Edit `pyproject.toml`,在 `[project]` 之後加:

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["art_source/pipeline"]
```

- [ ] **Step 2: Create empty test package**

```bash
mkdir -p tests
```

Create `tests/__init__.py` — 空檔。

- [ ] **Step 3: Create conftest with manifest isolation fixture**

Create `tests/conftest.py`:

```python
"""Shared pytest fixtures."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import pytest


@pytest.fixture
def isolated_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect manifest.json to tmp_path so tests don't touch real output/."""
    import manifest as m

    fake = tmp_path / "manifest.json"
    monkeypatch.setattr(m, "manifest_path", lambda: fake)
    monkeypatch.setattr(m, "output_dir", lambda: tmp_path)
    yield fake
```

- [ ] **Step 4: Sync deps and verify pytest runs**

Run: `uv sync`
Run: `uv run pytest --collect-only`
Expected: 0 tests collected, no errors.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock tests/__init__.py tests/conftest.py
git commit -m "test: add pytest infrastructure for art pipeline"
```

---

## Task 2: Manifest Stages Support

**Files:**
- Modify: `art_source/pipeline/manifest.py`
- Test: `tests/test_manifest_stages.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_manifest_stages.py`:

```python
"""Tests for manifest stage tracking."""
from __future__ import annotations

from pathlib import Path

import manifest


def test_mark_stage_writes_to_manifest(isolated_manifest: Path) -> None:
    manifest.upsert_character("alice", {"character_id": "uuid-1"})
    manifest.mark_stage(
        asset_type="character",
        name="alice",
        stage_name="generate_8dir_base",
        paths=["characters/alice/rotations/south.png"],
    )
    char = manifest.get_character("alice")
    assert char is not None
    stages = char["stages"]
    assert "generate_8dir_base" in stages
    assert stages["generate_8dir_base"]["paths"] == [
        "characters/alice/rotations/south.png"
    ]
    assert "completed_at" in stages["generate_8dir_base"]


def test_get_completed_stages_empty(isolated_manifest: Path) -> None:
    manifest.upsert_character("bob", {"character_id": "uuid-2"})
    assert manifest.get_completed_stages("character", "bob") == []


def test_get_completed_stages_returns_names_in_order(isolated_manifest: Path) -> None:
    manifest.upsert_character("carol", {"character_id": "uuid-3"})
    manifest.mark_stage("character", "carol", "stage_a", ["p1"])
    manifest.mark_stage("character", "carol", "stage_b", ["p2"])
    completed = manifest.get_completed_stages("character", "carol")
    assert completed == ["stage_a", "stage_b"]


def test_mark_stage_unknown_asset_type_raises(isolated_manifest: Path) -> None:
    import pytest
    with pytest.raises(ValueError, match="unknown asset_type"):
        manifest.mark_stage("widget", "x", "s", [])


def test_mark_stage_unknown_name_raises(isolated_manifest: Path) -> None:
    import pytest
    with pytest.raises(KeyError, match="not found"):
        manifest.mark_stage("character", "ghost", "s", [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_manifest_stages.py -v`
Expected: FAIL — `mark_stage` / `get_completed_stages` not defined.

- [ ] **Step 3: Implement `mark_stage` and `get_completed_stages`**

Edit `art_source/pipeline/manifest.py`,在 `def remove_object` 之後加:

```python
# === Stage tracking ===


_ASSET_KEY: dict[str, str] = {
    "character": "characters",
    "tileset": "tilesets",
    "object": "objects",
}


def mark_stage(
    asset_type: str,
    name: str,
    stage_name: str,
    paths: list[str],
) -> None:
    """記錄某資產某 stage 已完成,寫入 manifest。

    asset_type: "character" | "tileset" | "object"
    paths: 該 stage 產出的檔案路徑(相對 project root)
    """
    key = _ASSET_KEY.get(asset_type)
    if key is None:
        raise ValueError(f"unknown asset_type: {asset_type}")
    data = load()
    if name not in data[key]:
        raise KeyError(f"{asset_type} '{name}' not found in manifest")
    entry = data[key][name]
    stages = entry.setdefault("stages", {})
    stages[stage_name] = {
        "completed_at": now_iso(),
        "paths": paths,
    }
    entry["updated_at"] = now_iso()
    save(data)


def get_completed_stages(asset_type: str, name: str) -> list[str]:
    """回傳已完成 stage 名,依 manifest 寫入順序。"""
    key = _ASSET_KEY.get(asset_type)
    if key is None:
        raise ValueError(f"unknown asset_type: {asset_type}")
    data = load()
    entry = data[key].get(name, {})
    stages = entry.get("stages", {})
    return list(stages.keys())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_manifest_stages.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add art_source/pipeline/manifest.py tests/test_manifest_stages.py
git commit -m "feat: add stage tracking to manifest"
```

---

## Task 3: Pixellab Client Cleanup + New Wrappers

**Files:**
- Modify: `art_source/pipeline/pixellab_client.py`
- Test: `tests/test_pixellab_client_wrappers.py`

- [ ] **Step 1: Write tests for new wrappers (mock HTTP)**

Create `tests/test_pixellab_client_wrappers.py`:

```python
"""Tests for new client wrappers (HTTP mocked)."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import pixellab_client as plab


@patch("pixellab_client.requests.post")
def test_submit_character_4dir_calls_correct_url(mock_post: MagicMock) -> None:
    mock_post.return_value = MagicMock(
        status_code=200, json=lambda: {"character_id": "id-4dir"}
    )
    char_id = plab.submit_character_4dir(
        token="t", description="desc", size=64, view="high_top_down"
    )
    assert char_id == "id-4dir"
    args, kwargs = mock_post.call_args
    assert args[0] == plab.CREATE_CHAR_4DIR_URL
    assert kwargs["json"]["description"] == "desc"


@patch("pixellab_client.requests.post")
def test_submit_character_4dir_invalid_view_raises(mock_post: MagicMock) -> None:
    with pytest.raises(ValueError, match="view"):
        plab.submit_character_4dir(token="t", description="d", view="weird")


@patch("pixellab_client.requests.post")
def test_submit_character_4dir_no_id_raises(mock_post: MagicMock) -> None:
    mock_post.return_value = MagicMock(status_code=200, json=lambda: {})
    with pytest.raises(RuntimeError, match="character_id"):
        plab.submit_character_4dir(token="t", description="d")


@patch("pixellab_client.requests.post")
def test_submit_iso_tile_returns_id(mock_post: MagicMock) -> None:
    mock_post.return_value = MagicMock(
        status_code=200, json=lambda: {"object_id": "iso-1"}
    )
    obj_id = plab.submit_iso_tile(token="t", description="lantern", size=32)
    assert obj_id == "iso-1"


def test_dead_v1_helpers_removed() -> None:
    assert not hasattr(plab, "call_pixflux"), "call_pixflux should be deleted"
    assert not hasattr(plab, "call_rotate"), "call_rotate should be deleted"
    assert not hasattr(plab, "call_animate_with_text_v3"), \
        "call_animate_with_text_v3 should be deleted"
    assert not hasattr(plab, "PIXFLUX_URL")
    assert not hasattr(plab, "ROTATE_URL")
    assert not hasattr(plab, "ANIMATE_TEXT_V3_URL")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pixellab_client_wrappers.py -v`
Expected: FAIL — `submit_character_4dir` / `submit_iso_tile` missing; dead-code assertions fail because v1 helpers still exist.

- [ ] **Step 3: Delete v1 dead code**

Edit `art_source/pipeline/pixellab_client.py`:

- 刪除 URL 常數 `PIXFLUX_URL`、`ROTATE_URL`、`ANIMATE_TEXT_V3_URL`(第 36-38 行附近)
- 刪除函式 `call_pixflux`(第 176-194 行)
- 刪除函式 `call_rotate`(第 197-215 行)
- 刪除常數 `ROTATE_VALID_SIZES`(第 53 行)、`ANIMATE_V3_PIXEL_BUDGET`(第 54 行)
- 刪除函式 `call_animate_with_text_v3`(第 280-301 行)

確認 `CREATE_CHAR_4DIR_URL` 在第 42 行附近仍保留,並新增 `CREATE_ISO_TILE_URL`:

```python
CREATE_ISO_TILE_URL: str = f"{V2_BASE}/create-isometric-tile"
```

- [ ] **Step 4: Add `submit_character_4dir`**

在 `submit_character_8dir` 之後加(同檔):

```python
def submit_character_4dir(
    token: str,
    description: str,
    size: int = 64,
    view: str = "high_top_down",
    proportions_preset: str = "cartoon",
    outline: str | None = "single_color_outline",
    shading: str | None = "medium_shading",
    detail: str | None = "detailed",
    text_guidance_scale: float = 8.0,
) -> str:
    """提交建 4 方向角色,回傳 character_id;不等完成。

    與 submit_character_8dir 相同介面,只生 4 個基本方向(N/S/E/W),
    Pixellab credit ~50% 較便宜。注意:character_id 與 8-dir 端點不通用,
    日後升級成移動 NPC 需重新 create_character。
    """
    if view not in ("low_top_down", "high_top_down", "side"):
        raise ValueError(f"view 必須 low_top_down/high_top_down/side,收到 {view}")
    payload: dict[str, Any] = {
        "description": description,
        "image_size": {"width": size, "height": size},
        "view": view,
        "proportions": {"type": "preset", "name": proportions_preset},
        "text_guidance_scale": text_guidance_scale,
    }
    if outline:
        payload["outline"] = outline
    if shading:
        payload["shading"] = shading
    if detail:
        payload["detail"] = detail

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(CREATE_CHAR_4DIR_URL, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(
            f"create-character-4dir → HTTP {r.status_code}: {r.text[:500]}"
        )
    char_id = r.json().get("character_id", "")
    if not char_id:
        raise RuntimeError(f"回應無 character_id: {r.json()}")
    return char_id
```

- [ ] **Step 5: Add `submit_iso_tile`**

在檔案末尾加:

```python
def submit_iso_tile(
    token: str,
    description: str,
    size: int = 32,
    text_guidance_scale: float = 8.0,
) -> str:
    """提交建單格 isometric tile(含 prop / 小物件),回傳 object_id。

    用於小型 iso 物件(燈籠、攤車裝飾等)。大建築仍走 create-map-object。
    """
    payload: dict[str, Any] = {
        "description": description,
        "image_size": {"width": size, "height": size},
        "text_guidance_scale": text_guidance_scale,
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r = requests.post(CREATE_ISO_TILE_URL, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(
            f"create-isometric-tile → HTTP {r.status_code}: {r.text[:500]}"
        )
    obj_id = r.json().get("object_id") or r.json().get("id", "")
    if not obj_id:
        raise RuntimeError(f"回應無 object_id: {r.json()}")
    return obj_id
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_pixellab_client_wrappers.py -v`
Expected: 5 passed.

也跑全測試確認沒打到別的:

Run: `uv run pytest -v`
Expected: 全部 passed。

- [ ] **Step 7: Commit**

```bash
git add art_source/pipeline/pixellab_client.py tests/test_pixellab_client_wrappers.py
git commit -m "refactor: drop v1 dead code, add 4dir + iso_tile wrappers"
```

---

## Task 4: MCP Server Updates

**Files:**
- Modify: `art_source/pipeline/mcp_server.py`

- [ ] **Step 1: Add `directions` parameter to `create_character`**

編輯 `mcp_server.py`,把 `create_character` 簽名與內部 submit 改為:

把這一段:

```python
def create_character(
    name: str,
    description: str,
    preset: str = "npc",
    size: int = 64,
    view: str = "high_top_down",
    proportions: str = "cartoon",
) -> dict[str, Any]:
```

改成:

```python
def create_character(
    name: str,
    description: str,
    preset: str = "npc",
    size: int = 64,
    view: str = "high_top_down",
    proportions: str = "cartoon",
    directions: int = 8,
) -> dict[str, Any]:
```

並在 docstring 末尾加一行:

```
      directions: 4 或 8(預設 8)。4 用於確認永不移動的劇情背景 NPC,
                  省 ~50% Pixellab credit;但 character_id 與 8-dir 端點不通用,
                  日後想加 walk 動畫須重建。
```

把這一段:

```python
    char_id: str = plab.submit_character_8dir(
        token=token,
        description=description,
        size=size,
        view=view,
        proportions_preset=proportions,
    )
```

改成:

```python
    if directions == 4:
        char_id = plab.submit_character_4dir(
            token=token,
            description=description,
            size=size,
            view=view,
            proportions_preset=proportions,
        )
    elif directions == 8:
        char_id = plab.submit_character_8dir(
            token=token,
            description=description,
            size=size,
            view=view,
            proportions_preset=proportions,
        )
    else:
        return {
            "status": "error",
            "message": f"directions 必須 4 或 8,收到 {directions}",
        }
```

並在 `manifest.upsert_character(name=name, fields={...})` 第一次呼叫的 fields 裡加 `"directions": directions,`。

- [ ] **Step 2: Add `create_iso_prop` MCP tool**

在 `create_building` 之後加:

```python
@mcp.tool()
def create_iso_prop(
    name: str,
    description: str,
    size: int = 32,
) -> dict[str, Any]:
    """產生單格 isometric prop(燈籠、攤車裝飾、小物件)。

    使用 Pixellab v2 create-isometric-tile 端點,**原生 iso 視角**。
    與 create_building 不同:適合單格小物;大建築仍用 create_building 的 high_top_down。

    參數:
      name: 物件名(如 "red_lantern")
      description: 外觀描述
      size: 像素大小(建議 16-64,預設 32)
    """
    if manifest.get_object(name):
        return {
            "status": "exists",
            "message": f"object '{name}' 已存在",
            "object": manifest.get_object(name),
        }

    token: str = plab.load_token()
    object_id: str = plab.submit_iso_tile(
        token=token,
        description=description,
        size=size,
    )

    manifest.upsert_object(
        name=name,
        fields={
            "object_id": object_id,
            "description": description,
            "kind": "iso_prop",
            "size": {"width": size, "height": size},
            "status": "pending",
        },
    )

    meta: dict[str, Any] = plab.wait_for_object(token, object_id)

    out_dir: Path = manifest.object_dir(name)
    out_dir.mkdir(parents=True, exist_ok=True)
    img_path: Path = out_dir / f"{name}.png"

    img_field: Any = meta.get("image") or meta.get("image_url")
    if isinstance(img_field, dict):
        plab.b64_to_img(img_field.get("base64", "")).save(img_path)
    elif isinstance(img_field, str) and img_field.startswith("http"):
        import requests
        r = requests.get(
            img_field, headers={"Authorization": f"Bearer {token}"}, timeout=60
        )
        img_path.write_bytes(r.content)
    else:
        (out_dir / "raw_response.json").write_text(str(meta), encoding="utf-8")
        return {
            "status": "error",
            "message": "無法解析 iso_prop 圖片欄位",
            "object_id": object_id,
        }

    pp.chroma_key_file(img_path)

    manifest.upsert_object(
        name=name,
        fields={
            "status": "completed",
            "local_path": str(img_path.relative_to(plab.project_root())),
        },
    )

    return {
        "status": "completed",
        "name": name,
        "object_id": object_id,
        "local_path": str(img_path.relative_to(plab.project_root())),
    }
```

- [ ] **Step 3: Smoke import**

Run: `uv run python -c "import sys; sys.path.insert(0, 'art_source/pipeline'); import mcp_server; print('OK')"`
Expected: `OK` 印出,無 import 錯誤。

- [ ] **Step 4: Commit**

```bash
git add art_source/pipeline/mcp_server.py
git commit -m "feat: add directions param + create_iso_prop MCP tool"
```

---

## Task 5: Stage Framework

**Files:**
- Create: `art_source/pipeline/orchestrators/__init__.py`
- Create: `art_source/pipeline/orchestrators/_common.py`
- Test: `tests/test_stage_framework.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_stage_framework.py`:

```python
"""Tests for orchestrator stage framework."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "art_source" / "pipeline")
)

import manifest
from orchestrators import _common as oc


def _ctx(tmp_path: Path) -> oc.StageContext:
    return oc.StageContext(
        asset_type="character",
        name="test_npc",
        review_mode="none",
        resume_from=None,
        skip_set=set(),
        force_restart=set(),
    )


def test_stage_runs_when_review_mode_none(
    isolated_manifest: Path, tmp_path: Path
) -> None:
    manifest.upsert_character("test_npc", {"character_id": "id"})
    calls: list[str] = []

    @oc.stage("first")
    def first_stage(ctx: oc.StageContext) -> list[str]:
        calls.append("first")
        return ["p1"]

    ctx = _ctx(tmp_path)
    first_stage(ctx)
    assert calls == ["first"]
    assert "first" in manifest.get_completed_stages("character", "test_npc")


def test_stage_skips_when_completed_and_no_force(
    isolated_manifest: Path, tmp_path: Path
) -> None:
    manifest.upsert_character("test_npc", {"character_id": "id"})
    manifest.mark_stage("character", "test_npc", "first", ["existing"])

    calls: list[str] = []

    @oc.stage("first")
    def first_stage(ctx: oc.StageContext) -> list[str]:
        calls.append("first")
        return ["new"]

    ctx = _ctx(tmp_path)
    first_stage(ctx)
    assert calls == [], "已完成 stage 不應重跑"


def test_stage_reruns_when_in_force_restart(
    isolated_manifest: Path, tmp_path: Path
) -> None:
    manifest.upsert_character("test_npc", {"character_id": "id"})
    manifest.mark_stage("character", "test_npc", "first", ["old"])

    calls: list[str] = []

    @oc.stage("first")
    def first_stage(ctx: oc.StageContext) -> list[str]:
        calls.append("first")
        return ["new"]

    ctx = _ctx(tmp_path)
    ctx.force_restart = {"first"}
    first_stage(ctx)
    assert calls == ["first"]


def test_stage_exits_after_run_when_review_mode_stage(
    isolated_manifest: Path, tmp_path: Path
) -> None:
    manifest.upsert_character("test_npc", {"character_id": "id"})

    @oc.stage("only")
    def only_stage(ctx: oc.StageContext) -> list[str]:
        return ["p"]

    ctx = _ctx(tmp_path)
    ctx.review_mode = "stage"
    with pytest.raises(SystemExit) as exc:
        only_stage(ctx)
    assert exc.value.code == 0


def test_resume_from_skips_earlier_stages(
    isolated_manifest: Path, tmp_path: Path
) -> None:
    manifest.upsert_character("test_npc", {"character_id": "id"})
    calls: list[str] = []

    @oc.stage("a")
    def a(ctx: oc.StageContext) -> list[str]:
        calls.append("a"); return []

    @oc.stage("b")
    def b(ctx: oc.StageContext) -> list[str]:
        calls.append("b"); return []

    ctx = _ctx(tmp_path)
    ctx.skip_set = {"a"}  # resume_from=b 解析後的結果
    a(ctx)
    b(ctx)
    assert calls == ["b"]


def test_compute_skip_set_from_resume_from() -> None:
    skip = oc.compute_skip_set(
        all_stages=["a", "b", "c"], resume_from="b"
    )
    assert skip == {"a"}


def test_compute_skip_set_unknown_resume_raises() -> None:
    with pytest.raises(ValueError, match="unknown stage"):
        oc.compute_skip_set(all_stages=["a", "b"], resume_from="zzz")


def test_parse_common_args_defaults() -> None:
    ns = oc.parse_common_args(["--name", "alice"])
    assert ns.name == "alice"
    assert ns.review_mode == "stage"
    assert ns.resume_from is None
    assert ns.force_restart_stage == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
mkdir -p art_source/pipeline/orchestrators
```

Create empty `art_source/pipeline/orchestrators/__init__.py`.

Run: `uv run pytest tests/test_stage_framework.py -v`
Expected: FAIL — `_common` module not found.

- [ ] **Step 3: Implement `_common.py`**

Create `art_source/pipeline/orchestrators/_common.py`:

```python
"""Shared stage framework for art pipeline orchestrators.

提供:
  - @stage 裝飾器:自動讀已完成 stage、寫入完成記錄、按 review-mode 暫停
  - parse_common_args:統一 CLI 介面
  - StageContext:跨 stage 傳遞狀態的 dataclass
  - compute_skip_set:把 --resume-from 轉成要跳過的 stage 集合
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Literal

import manifest


ReviewMode = Literal["none", "stage", "step"]


@dataclass
class StageContext:
    asset_type: str  # "character" | "tileset" | "object"
    name: str
    review_mode: ReviewMode
    resume_from: str | None
    skip_set: set[str]
    force_restart: set[str]
    args: argparse.Namespace | None = None
    extra: dict[str, Any] = field(default_factory=dict)


def stage(stage_name: str) -> Callable[[Callable[..., list[str]]], Callable[..., None]]:
    """裝飾器:把一個函式登錄為 pipeline stage。

    被裝飾函式:
      - 接受 ctx: StageContext
      - 回傳 list[str](該 stage 產出的檔案路徑)

    框架負責:
      - skip_set 中的 stage 直接跳過(已 resume)
      - 已在 manifest 完成且不在 force_restart 的 stage 直接跳過
      - 跑完寫入 manifest.mark_stage
      - review_mode == "stage" 跑完印路徑後 sys.exit(0)
    """
    def decorator(fn: Callable[..., list[str]]) -> Callable[..., None]:
        @wraps(fn)
        def wrapper(ctx: StageContext) -> None:
            if stage_name in ctx.skip_set:
                print(f"[skip] {stage_name}(resume-from)")
                return
            completed = manifest.get_completed_stages(ctx.asset_type, ctx.name)
            if stage_name in completed and stage_name not in ctx.force_restart:
                print(f"[skip] {stage_name}(已完成於 manifest)")
                return

            print(f"[run]  {stage_name} ...")
            paths = fn(ctx)
            manifest.mark_stage(ctx.asset_type, ctx.name, stage_name, paths)
            print(f"[done] {stage_name} → {paths}")

            if ctx.review_mode == "stage":
                print(
                    f"\n--- review-mode=stage:於 {stage_name} 暫停 ---\n"
                    f"檢視產出後,以 --resume-from <next-stage> 繼續。"
                )
                sys.exit(0)
        return wrapper
    return decorator


def compute_skip_set(all_stages: list[str], resume_from: str | None) -> set[str]:
    """把 --resume-from 轉成要跳過的 stage 集合。

    resume_from=None → 空集合
    resume_from="b" with all_stages=["a","b","c"] → {"a"}
    """
    if resume_from is None:
        return set()
    if resume_from not in all_stages:
        raise ValueError(
            f"unknown stage '{resume_from}';available: {all_stages}"
        )
    idx = all_stages.index(resume_from)
    return set(all_stages[:idx])


def parse_common_args(argv: list[str] | None = None) -> argparse.Namespace:
    """共用 CLI 參數解析。Pipeline 自身可在呼叫前先 add_argument 自家專屬。"""
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--name", required=True, help="資產名(manifest key)")
    parser.add_argument(
        "--review-mode",
        choices=["none", "stage", "step"],
        default="stage",
        help="none=一路到底;stage=每階段停;step=每 API 呼叫停",
    )
    parser.add_argument(
        "--resume-from", default=None, help="從指定 stage 起跑,前面 stage 跳過"
    )
    parser.add_argument(
        "--force-restart-stage",
        action="append",
        default=[],
        help="強制重跑某 stage(可多次指定)",
    )
    return parser.parse_args(argv)


def make_context(
    asset_type: str,
    args: argparse.Namespace,
    all_stages: list[str],
) -> StageContext:
    """從 parsed args 建 StageContext。"""
    return StageContext(
        asset_type=asset_type,
        name=args.name,
        review_mode=args.review_mode,
        resume_from=args.resume_from,
        skip_set=compute_skip_set(all_stages, args.resume_from),
        force_restart=set(args.force_restart_stage),
        args=args,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stage_framework.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add art_source/pipeline/orchestrators/__init__.py \
        art_source/pipeline/orchestrators/_common.py \
        tests/test_stage_framework.py
git commit -m "feat: add stage framework for orchestrators"
```

---

## Task 6: Autotile Orchestrator

**Files:**
- Create: `art_source/pipeline/orchestrators/autotile.py`

- [ ] **Step 1: Implement `autotile.py`**

Create `art_source/pipeline/orchestrators/autotile.py`:

```python
"""Pipeline 1: Autotile orchestrator.

Stages:
  1. generate_atlas      — Pixellab create-topdown-tileset(async)
  2. iso_project         — PIL 4×4 affine 投影成菱形 atlas
  3. verify_in_godot     — 印 Godot import 提示(不做事)

CLI:
  uv run python art_source/pipeline/orchestrators/autotile.py \\
      --name market_grass_asphalt \\
      --lower "green grass texture" \\
      --upper "dark asphalt road" \\
      [--transition-size 0.25] [--transition-description "grey concrete curb"] \\
      [--tile-size 16] [--review-mode stage]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import manifest
import pixellab_client as plab
import post_process as pp
from orchestrators._common import (
    StageContext,
    make_context,
    parse_common_args,
    stage,
)


STAGES: list[str] = ["generate_atlas", "iso_project", "verify_in_godot"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--lower", help="下層地形描述(首次必填)")
    parser.add_argument("--upper", help="上層地形描述(首次必填)")
    parser.add_argument("--transition-size", type=float, default=0.0)
    parser.add_argument("--transition-description", default=None)
    parser.add_argument("--tile-size", type=int, default=16)
    parser.add_argument(
        "--review-mode", choices=["none", "stage", "step"], default="stage"
    )
    parser.add_argument("--resume-from", default=None)
    parser.add_argument("--force-restart-stage", action="append", default=[])
    return parser.parse_args()


@stage("generate_atlas")
def generate_atlas(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    if not args.lower or not args.upper:
        raise SystemExit("首次跑 generate_atlas 須提供 --lower 與 --upper")

    token = plab.load_token()
    tileset_id = plab.submit_topdown_tileset(
        token=token,
        lower_description=args.lower,
        upper_description=args.upper,
        transition_size=args.transition_size,
        transition_description=args.transition_description,
        tile_width=args.tile_size,
        tile_height=args.tile_size,
    )
    manifest.upsert_tileset(
        name=ctx.name,
        fields={
            "tileset_id": tileset_id,
            "lower": args.lower,
            "upper": args.upper,
            "tile_size": args.tile_size,
            "status": "pending",
        },
    )
    meta = plab.wait_for_tileset(token, tileset_id)

    out_dir = manifest.tileset_dir(ctx.name)
    out_dir.mkdir(parents=True, exist_ok=True)
    atlas_path = out_dir / f"{ctx.name}_topdown.png"
    field_value = meta.get("image") or meta.get("atlas") or meta.get("image_url")
    if isinstance(field_value, dict):
        plab.b64_to_img(field_value.get("base64", "")).save(atlas_path)
    elif isinstance(field_value, str) and field_value.startswith("http"):
        import requests
        r = requests.get(
            field_value, headers={"Authorization": f"Bearer {token}"}, timeout=60
        )
        atlas_path.write_bytes(r.content)
    else:
        (out_dir / "raw_response.json").write_text(str(meta), encoding="utf-8")
        raise SystemExit(f"無法解析 atlas 圖片欄位 — 見 {out_dir}/raw_response.json")

    manifest.upsert_tileset(
        name=ctx.name,
        fields={
            "status": "atlas_ready",
            "topdown_path": str(atlas_path.relative_to(plab.project_root())),
        },
    )
    return [str(atlas_path.relative_to(plab.project_root()))]


@stage("iso_project")
def iso_project(ctx: StageContext) -> list[str]:
    out_dir = manifest.tileset_dir(ctx.name)
    atlas_path = out_dir / f"{ctx.name}_topdown.png"
    iso_path = out_dir / f"{ctx.name}_iso.png"
    pp.project_atlas_file(atlas_path, iso_path, cols=4, rows=4)
    manifest.upsert_tileset(
        name=ctx.name,
        fields={
            "iso_path": str(iso_path.relative_to(plab.project_root())),
            "status": "completed",
        },
    )
    return [str(iso_path.relative_to(plab.project_root()))]


@stage("verify_in_godot")
def verify_in_godot(ctx: StageContext) -> list[str]:
    out_dir = manifest.tileset_dir(ctx.name)
    iso_path = out_dir / f"{ctx.name}_iso.png"
    print(
        f"\n→ 將 {iso_path} import 到 Godot,搭 TileMapDual addon。"
        f"\n  參考 docs/tilemapdual-guide.md"
    )
    return [str(iso_path.relative_to(plab.project_root()))]


def main() -> None:
    plab.setup_console()
    args = parse_args()
    ctx = make_context("tileset", args, STAGES)

    # 確保 manifest 條目存在(供 mark_stage 用)
    if not manifest.get_tileset(ctx.name):
        manifest.upsert_tileset(name=ctx.name, fields={"status": "init"})

    generate_atlas(ctx)
    iso_project(ctx)
    verify_in_godot(ctx)
    print(f"\n[autotile] {ctx.name} 完成。")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke import test**

Run:
```bash
uv run python -c "import sys; sys.path.insert(0, 'art_source/pipeline'); from orchestrators import autotile; print('OK')"
```
Expected: `OK`。

- [ ] **Step 3: --help works**

Run:
```bash
uv run python art_source/pipeline/orchestrators/autotile.py --help
```
Expected: 顯示參數說明,無錯誤。

- [ ] **Step 4: Commit**

```bash
git add art_source/pipeline/orchestrators/autotile.py
git commit -m "feat: add autotile orchestrator"
```

---

## Task 7: Prop Orchestrator

**Files:**
- Create: `art_source/pipeline/orchestrators/prop.py`

- [ ] **Step 1: Implement `prop.py`**

Create `art_source/pipeline/orchestrators/prop.py`:

```python
"""Pipeline 2: Prop orchestrator(building 大建築 + iso_prop 小單格)。

Stages:
  1. generate_object  — building → create-map-object;iso_prop → create-isometric-tile
  2. chroma_key       — PIL 去背(若 API 有殘留底色)

CLI:
  uv run python art_source/pipeline/orchestrators/prop.py \\
      --name muzha_shophouse --kind building \\
      --description "traditional taiwanese shophouse, red brick" \\
      --width 128 --height 128 [--review-mode stage]

  uv run python art_source/pipeline/orchestrators/prop.py \\
      --name red_lantern --kind iso_prop \\
      --description "red paper lantern with gold tassel" \\
      --size 32
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import manifest
import pixellab_client as plab
import post_process as pp
from orchestrators._common import (
    StageContext,
    make_context,
    parse_common_args,
    stage,
)


STAGES: list[str] = ["generate_object", "chroma_key"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--kind", choices=["building", "iso_prop"], required=True)
    p.add_argument("--description", default=None)
    p.add_argument("--width", type=int, default=96)
    p.add_argument("--height", type=int, default=96)
    p.add_argument("--size", type=int, default=32, help="iso_prop 用")
    p.add_argument("--view", default="high_top_down", help="building 用")
    p.add_argument(
        "--review-mode", choices=["none", "stage", "step"], default="stage"
    )
    p.add_argument("--resume-from", default=None)
    p.add_argument("--force-restart-stage", action="append", default=[])
    return p.parse_args()


def _download_image(token: str, meta: dict[str, Any], dst: Path) -> None:
    img_field = meta.get("image") or meta.get("image_url")
    if isinstance(img_field, dict):
        plab.b64_to_img(img_field.get("base64", "")).save(dst)
        return
    if isinstance(img_field, str) and img_field.startswith("http"):
        import requests
        r = requests.get(
            img_field, headers={"Authorization": f"Bearer {token}"}, timeout=60
        )
        dst.write_bytes(r.content)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    (dst.parent / "raw_response.json").write_text(str(meta), encoding="utf-8")
    raise SystemExit(f"無法解析 image 欄位 — 見 {dst.parent}/raw_response.json")


@stage("generate_object")
def generate_object(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    if not args.description:
        raise SystemExit("首次跑 generate_object 須提供 --description")

    token = plab.load_token()
    out_dir = manifest.object_dir(ctx.name)
    out_dir.mkdir(parents=True, exist_ok=True)
    img_path = out_dir / f"{ctx.name}.png"

    if args.kind == "building":
        object_id = plab.submit_map_object(
            token=token,
            description=args.description,
            width=args.width,
            height=args.height,
            view=args.view,
        )
        manifest.upsert_object(
            name=ctx.name,
            fields={
                "object_id": object_id,
                "kind": "building",
                "description": args.description,
                "view": args.view,
                "size": {"width": args.width, "height": args.height},
                "status": "pending",
            },
        )
    else:  # iso_prop
        object_id = plab.submit_iso_tile(
            token=token, description=args.description, size=args.size
        )
        manifest.upsert_object(
            name=ctx.name,
            fields={
                "object_id": object_id,
                "kind": "iso_prop",
                "description": args.description,
                "size": {"width": args.size, "height": args.size},
                "status": "pending",
            },
        )

    meta = plab.wait_for_object(token, object_id)
    _download_image(token, meta, img_path)
    return [str(img_path.relative_to(plab.project_root()))]


@stage("chroma_key")
def chroma_key(ctx: StageContext) -> list[str]:
    img_path = manifest.object_dir(ctx.name) / f"{ctx.name}.png"
    pp.chroma_key_file(img_path)
    manifest.upsert_object(
        name=ctx.name,
        fields={
            "status": "completed",
            "local_path": str(img_path.relative_to(plab.project_root())),
        },
    )
    return [str(img_path.relative_to(plab.project_root()))]


def main() -> None:
    plab.setup_console()
    args = parse_args()
    ctx = make_context("object", args, STAGES)

    if not manifest.get_object(ctx.name):
        manifest.upsert_object(name=ctx.name, fields={"status": "init"})

    generate_object(ctx)
    chroma_key(ctx)
    print(f"\n[prop:{args.kind}] {ctx.name} 完成。")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke checks**

Run:
```bash
uv run python -c "import sys; sys.path.insert(0, 'art_source/pipeline'); from orchestrators import prop; print('OK')"
uv run python art_source/pipeline/orchestrators/prop.py --help
```
Expected: 兩條都成功。

- [ ] **Step 3: Commit**

```bash
git add art_source/pipeline/orchestrators/prop.py
git commit -m "feat: add prop orchestrator (building + iso_prop)"
```

---

## Task 8: Static NPC Orchestrator

**Files:**
- Create: `art_source/pipeline/orchestrators/npc_static.py`

- [ ] **Step 1: Implement `npc_static.py`**

Create `art_source/pipeline/orchestrators/npc_static.py`:

```python
"""Pipeline 3: Static NPC orchestrator(劇情背景 NPC,4 向 idle)。

Stages:
  1. generate_4dir_base   — create-character(4-dir 或 8-dir,看 --directions)
  2. add_idle_animation   — animate-character 4 向 idle(可 --no-idle 關)
  3. compile_spritesheet  — 呼叫 scripts/generate_spritesheet.py

CLI:
  uv run python art_source/pipeline/orchestrators/npc_static.py \\
      --name shopkeeper_li \\
      --description "elderly taiwanese male shopkeeper, blue shirt" \\
      [--directions 4] [--no-idle] [--review-mode stage]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import manifest
import pixellab_client as plab
import post_process as pp
from orchestrators._common import StageContext, make_context, stage


CARDINAL_DIRECTIONS: list[str] = ["south", "east", "north", "west"]
STAGES: list[str] = ["generate_4dir_base", "add_idle_animation", "compile_spritesheet"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--description", default=None)
    p.add_argument("--directions", type=int, choices=[4, 8], default=8)
    p.add_argument("--view", default="high_top_down")
    p.add_argument("--proportions", default="cartoon")
    p.add_argument("--no-idle", action="store_true")
    p.add_argument("--idle-frame-count", type=int, default=4)
    p.add_argument(
        "--review-mode", choices=["none", "stage", "step"], default="stage"
    )
    p.add_argument("--resume-from", default=None)
    p.add_argument("--force-restart-stage", action="append", default=[])
    return p.parse_args()


@stage("generate_4dir_base")
def generate_4dir_base(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    if not args.description:
        raise SystemExit("首次跑須提供 --description")

    token = plab.load_token()
    if args.directions == 4:
        char_id = plab.submit_character_4dir(
            token=token, description=args.description,
            view=args.view, proportions_preset=args.proportions,
        )
    else:
        char_id = plab.submit_character_8dir(
            token=token, description=args.description,
            view=args.view, proportions_preset=args.proportions,
        )
    manifest.upsert_character(
        name=ctx.name,
        fields={
            "character_id": char_id,
            "preset": "npc",
            "directions": args.directions,
            "view": args.view,
            "proportions": args.proportions,
            "description": args.description,
            "status": "pending",
        },
    )
    plab.wait_for_character(token, char_id)
    out_dir = manifest.character_dir(ctx.name) / "rotations"
    saved = plab.download_character_rotations(token, char_id, out_dir)
    for p in saved.values():
        pp.chroma_key_file(p)
    manifest.upsert_character(
        name=ctx.name,
        fields={
            "status": "base_ready",
            "rotations": list(saved.keys()),
            "local_path": str(
                manifest.character_dir(ctx.name).relative_to(plab.project_root())
            ),
        },
    )
    return [str(p.relative_to(plab.project_root())) for p in saved.values()]


@stage("add_idle_animation")
def add_idle_animation(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    if args.no_idle:
        print("--no-idle 指定,略過 idle 動畫")
        return []

    char = manifest.get_character(ctx.name)
    assert char is not None
    char_id: str = char["character_id"]
    token = plab.load_token()

    submitted = plab.submit_character_animation(
        token=token,
        character_id=char_id,
        action_description="idle",
        directions=CARDINAL_DIRECTIONS,
        frame_count=args.idle_frame_count,
    )
    saved_paths: list[str] = []
    for direction, job_id in zip(submitted["directions"], submitted["background_job_ids"]):
        result = plab.poll_background_job(token, job_id)
        images = result.get("images") or []
        anim_dir = manifest.character_dir(ctx.name) / "animations" / "idle" / direction
        anim_dir.mkdir(parents=True, exist_ok=True)
        for i, item in enumerate(images):
            b64 = item.get("base64") if isinstance(item, dict) else item
            img = plab.b64_to_img(b64)
            img = pp.chroma_key_bg(img)
            frame_path = anim_dir / f"frame_{i:03d}.png"
            img.save(frame_path)
            saved_paths.append(str(frame_path.relative_to(plab.project_root())))

    animations = char.get("animations", {})
    animations.setdefault("idle", [])
    for d in submitted["directions"]:
        if d not in animations["idle"]:
            animations["idle"].append(d)
    manifest.upsert_character(name=ctx.name, fields={"animations": animations})
    return saved_paths


@stage("compile_spritesheet")
def compile_spritesheet(ctx: StageContext) -> list[str]:
    char_dir = manifest.character_dir(ctx.name)
    script = plab.project_root() / "scripts" / "generate_spritesheet.py"
    if not script.exists():
        print(f"[warn] {script} 不存在,略過 spritesheet 編譯")
        return []
    cmd = ["uv", "run", "python", str(script), "--character-dir", str(char_dir)]
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    return [str(char_dir.relative_to(plab.project_root()))]


def main() -> None:
    plab.setup_console()
    args = parse_args()
    ctx = make_context("character", args, STAGES)

    if not manifest.get_character(ctx.name):
        manifest.upsert_character(name=ctx.name, fields={"status": "init"})

    generate_4dir_base(ctx)
    add_idle_animation(ctx)
    compile_spritesheet(ctx)
    print(f"\n[npc_static] {ctx.name} 完成。")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke checks**

Run:
```bash
uv run python -c "import sys; sys.path.insert(0, 'art_source/pipeline'); from orchestrators import npc_static; print('OK')"
uv run python art_source/pipeline/orchestrators/npc_static.py --help
```
Expected: 成功。

- [ ] **Step 3: Commit**

```bash
git add art_source/pipeline/orchestrators/npc_static.py
git commit -m "feat: add npc_static orchestrator"
```

---

## Task 9: Moving NPC Orchestrator

**Files:**
- Create: `art_source/pipeline/orchestrators/npc_moving.py`

- [ ] **Step 1: Implement `npc_moving.py`**

Create `art_source/pipeline/orchestrators/npc_moving.py`:

```python
"""Pipeline 4: Moving NPC orchestrator(player + 移動 NPC)。

Stages:
  1. generate_8dir_base   — create-character-with-8-directions
  2. add_idle_animation   — animate-character 4 向 idle
  3. add_walk_animation   — animate-character 8 向 walk
  4. compile_spritesheet  — 呼叫 scripts/generate_spritesheet.py

CLI:
  uv run python art_source/pipeline/orchestrators/npc_moving.py \\
      --name chen_ayi \\
      --description "middle-aged taiwanese market vendor woman, red floral shirt" \\
      [--review-mode stage]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import manifest
import pixellab_client as plab
import post_process as pp
from orchestrators._common import StageContext, make_context, stage


CARDINAL_DIRECTIONS: list[str] = ["south", "east", "north", "west"]
ALL_8_DIRECTIONS: list[str] = [
    "south", "south-east", "east", "north-east",
    "north", "north-west", "west", "south-west",
]
STAGES: list[str] = [
    "generate_8dir_base",
    "add_idle_animation",
    "add_walk_animation",
    "compile_spritesheet",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--description", default=None)
    p.add_argument("--view", default="high_top_down")
    p.add_argument("--proportions", default="cartoon")
    p.add_argument("--idle-frame-count", type=int, default=4)
    p.add_argument("--walk-frame-count", type=int, default=8)
    p.add_argument(
        "--review-mode", choices=["none", "stage", "step"], default="stage"
    )
    p.add_argument("--resume-from", default=None)
    p.add_argument("--force-restart-stage", action="append", default=[])
    return p.parse_args()


def _run_animation(
    ctx: StageContext,
    action: str,
    directions: list[str],
    frame_count: int,
) -> list[str]:
    char = manifest.get_character(ctx.name)
    assert char is not None
    char_id: str = char["character_id"]
    token = plab.load_token()

    submitted = plab.submit_character_animation(
        token=token,
        character_id=char_id,
        action_description=action,
        directions=directions,
        frame_count=frame_count,
    )
    saved_paths: list[str] = []
    for direction, job_id in zip(submitted["directions"], submitted["background_job_ids"]):
        result = plab.poll_background_job(token, job_id)
        images = result.get("images") or []
        anim_dir = manifest.character_dir(ctx.name) / "animations" / action / direction
        anim_dir.mkdir(parents=True, exist_ok=True)
        for i, item in enumerate(images):
            b64 = item.get("base64") if isinstance(item, dict) else item
            img = plab.b64_to_img(b64)
            img = pp.chroma_key_bg(img)
            frame_path = anim_dir / f"frame_{i:03d}.png"
            img.save(frame_path)
            saved_paths.append(str(frame_path.relative_to(plab.project_root())))

    animations = char.get("animations", {})
    animations.setdefault(action, [])
    for d in submitted["directions"]:
        if d not in animations[action]:
            animations[action].append(d)
    manifest.upsert_character(name=ctx.name, fields={"animations": animations})
    return saved_paths


@stage("generate_8dir_base")
def generate_8dir_base(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    if not args.description:
        raise SystemExit("首次跑須提供 --description")

    token = plab.load_token()
    char_id = plab.submit_character_8dir(
        token=token, description=args.description,
        view=args.view, proportions_preset=args.proportions,
    )
    manifest.upsert_character(
        name=ctx.name,
        fields={
            "character_id": char_id,
            "preset": "player",
            "directions": 8,
            "view": args.view,
            "proportions": args.proportions,
            "description": args.description,
            "status": "pending",
        },
    )
    plab.wait_for_character(token, char_id)
    out_dir = manifest.character_dir(ctx.name) / "rotations"
    saved = plab.download_character_rotations(token, char_id, out_dir)
    for p in saved.values():
        pp.chroma_key_file(p)
    manifest.upsert_character(
        name=ctx.name,
        fields={
            "status": "base_ready",
            "rotations": list(saved.keys()),
            "local_path": str(
                manifest.character_dir(ctx.name).relative_to(plab.project_root())
            ),
        },
    )
    return [str(p.relative_to(plab.project_root())) for p in saved.values()]


@stage("add_idle_animation")
def add_idle_animation(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    return _run_animation(ctx, "idle", CARDINAL_DIRECTIONS, args.idle_frame_count)


@stage("add_walk_animation")
def add_walk_animation(ctx: StageContext) -> list[str]:
    args = ctx.args
    assert args is not None
    return _run_animation(ctx, "walk", ALL_8_DIRECTIONS, args.walk_frame_count)


@stage("compile_spritesheet")
def compile_spritesheet(ctx: StageContext) -> list[str]:
    char_dir = manifest.character_dir(ctx.name)
    script = plab.project_root() / "scripts" / "generate_spritesheet.py"
    if not script.exists():
        print(f"[warn] {script} 不存在,略過 spritesheet 編譯")
        return []
    cmd = ["uv", "run", "python", str(script), "--character-dir", str(char_dir)]
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    return [str(char_dir.relative_to(plab.project_root()))]


def main() -> None:
    plab.setup_console()
    args = parse_args()
    ctx = make_context("character", args, STAGES)

    if not manifest.get_character(ctx.name):
        manifest.upsert_character(name=ctx.name, fields={"status": "init"})

    generate_8dir_base(ctx)
    add_idle_animation(ctx)
    add_walk_animation(ctx)
    compile_spritesheet(ctx)
    print(f"\n[npc_moving] {ctx.name} 完成。")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke checks**

Run:
```bash
uv run python -c "import sys; sys.path.insert(0, 'art_source/pipeline'); from orchestrators import npc_moving; print('OK')"
uv run python art_source/pipeline/orchestrators/npc_moving.py --help
```
Expected: 成功。

- [ ] **Step 3: Run all tests**

Run: `uv run pytest -v`
Expected: 全部 passed。

- [ ] **Step 4: Commit**

```bash
git add art_source/pipeline/orchestrators/npc_moving.py
git commit -m "feat: add npc_moving orchestrator"
```

---

## Task 10: Documentation Updates

**Files:**
- Modify: `art_source/pipeline/README.md`
- Modify: `docs/INDEX.md`

- [ ] **Step 1: Update `art_source/pipeline/README.md`**

在 README 開頭「## 架構」之後、「## 八個 MCP 工具」之前,插入新區塊:

```markdown
## 兩種使用方式

| 用途 | 工具 |
|---|---|
| **單張互動式生成**(對話中即時建一個 NPC / autotile) | MCP 工具(`mcp__muzharpg-pixellab__*`) |
| **多階段批次 / 可中斷續跑** | CLI orchestrator(`art_source/pipeline/orchestrators/*.py`) |

orchestrator 在每個 stage 完成後可暫停讓使用者檢視成果,確認後 `--resume-from` 繼續;或用 `--review-mode none` 一路跑完(批次模式)。

### Orchestrator 列表

| 檔案 | Pipeline | Stages |
|---|---|---|
| `orchestrators/autotile.py` | iso 地形 autotile | `generate_atlas` → `iso_project` → `verify_in_godot` |
| `orchestrators/prop.py` | 大建築 + iso 小 prop | `generate_object` → `chroma_key`(`--kind=building\|iso_prop`) |
| `orchestrators/npc_static.py` | 劇情靜態 NPC(4 向 idle) | `generate_4dir_base` → `add_idle_animation` → `compile_spritesheet`(`--directions 4\|8`) |
| `orchestrators/npc_moving.py` | 移動 NPC / player(8 向 walk + 4 向 idle) | `generate_8dir_base` → `add_idle_animation` → `add_walk_animation` → `compile_spritesheet` |

共用 CLI 旗標:
- `--review-mode {none,stage,step}` — 預設 `stage`(每階段停)
- `--resume-from <stage_name>` — 從某 stage 起跑
- `--force-restart-stage <stage_name>` — 強制重跑某已完成 stage(可多次)

範例:

```powershell
# 互動,每階段停
uv run python art_source/pipeline/orchestrators/npc_moving.py `
  --name chen_ayi --description "..." --review-mode stage

# 接續
uv run python art_source/pipeline/orchestrators/npc_moving.py `
  --name chen_ayi --resume-from add_walk_animation --review-mode stage

# 批次
uv run python art_source/pipeline/orchestrators/npc_static.py `
  --name path_npc --description "..." --directions 4 --review-mode none
```
```

並把現有「## 八個 MCP 工具」表格的標題改成「## 九個 MCP 工具」,在表格末加一列:

```
| `create_iso_prop(name, description, size)` | 單格 iso prop(燈籠等),原生 isometric 視角 |
```

- [ ] **Step 2: Update `docs/INDEX.md`**

在 INDEX.md 找到 art-pipeline-refactor-plan.md 條目附近,加一行指向新 spec 與 plan:

```markdown
- [Art pipeline orchestrators 設計](superpowers/specs/2026-05-05-art-pipeline-orchestrators-design.md) — CLI orchestrator 4 條(autotile/prop/npc_static/npc_moving),搭 stage/resume/批次模式
```

(具體插入位置依 INDEX.md 既有結構,放在「美術相關」區段)

- [ ] **Step 3: Commit**

```bash
git add art_source/pipeline/README.md docs/INDEX.md
git commit -m "docs: document orchestrators and updated MCP tool list"
```

---

## Task 11: End-to-End Smoke Verification

**Files:** 無新檔案。手動驗證。

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: 全部 passed,至少 17 個 test 通過。

- [ ] **Step 2: Verify MCP server still loads**

Run: `uv run python -c "import sys; sys.path.insert(0, 'art_source/pipeline'); import mcp_server; tools = [t for t in dir(mcp_server) if not t.startswith('_')]; print(tools)"`
Expected: 看到 `create_character`、`create_iso_prop`、`create_autotile`、`create_building` 等。

- [ ] **Step 3: All four orchestrator --help**

Run:
```bash
for f in autotile prop npc_static npc_moving; do
  echo "=== $f ==="
  uv run python art_source/pipeline/orchestrators/$f.py --help
done
```
Expected: 4 條都印出 help,無錯誤。

- [ ] **Step 4: Verify dead code is gone**

Run: `uv run python -c "import sys; sys.path.insert(0, 'art_source/pipeline'); import pixellab_client as p; assert not hasattr(p, 'call_pixflux'); assert not hasattr(p, 'call_rotate'); print('clean')"`
Expected: `clean`。

- [ ] **Step 5: Final commit if anything changed**

```bash
git status
# 若有未 commit 的小修正
git add -A
git commit -m "chore: final cleanup post-orchestrators"
```

---

## Self-Review Notes

**Spec coverage:**
- §3 Pipeline 1 ✓ Task 6
- §3 Pipeline 2 ✓ Task 7(含 building + iso_prop)
- §3 Pipeline 3 ✓ Task 8(含 directions 參數)
- §3 Pipeline 4 ✓ Task 9
- §4.2 Stage 框架 ✓ Task 5
- §4.3 Manifest stages ✓ Task 2
- §4.5 MCP 變更 + 死碼刪除 ✓ Tasks 3, 4
- §9 文件 ✓ Task 10

**Type consistency:** `mark_stage(asset_type, name, stage_name, paths)` 簽名在 Task 2 定義、Task 5 使用、Tasks 6-9 透過 `@stage` 間接呼叫,一致。`StageContext` 屬性(`asset_type`、`name`、`review_mode`、`resume_from`、`skip_set`、`force_restart`、`args`、`extra`)在 Task 5 定義,Tasks 6-9 使用一致。
