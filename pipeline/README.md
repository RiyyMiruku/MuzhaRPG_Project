# 美術生產 Pipeline

> 透過 Pixellab v2 API 產出角色、autotile、map 物件。所有資產由 [`art_source/manifest.json`](../art_source/manifest.json) 索引，使用者只需用「名字」操作。

## 架構

```
使用者
    │
    ├── tools/asset_dashboard/     (Web UI — 主介面)
    │       瀏覽資產、編輯 prompt、Remake、查 pipeline 進度
    │
    └── pipeline/orchestrators/   (CLI — 等值 raw access)
            │
            ├── pixellab_client.py  ── Pixellab v2 HTTP 端點封裝
            │       │
            │       │  HTTPS + Bearer token (從 .env 讀)
            │       ▼
            │     api.pixellab.ai
            │
            ├── post_process.py     ── PIL 後處理（去背、iso 投影）
            │
            └── manifest.py         ── art_source/manifest.json 索引
```

## 兩種介面

| 介面 | 用途 |
|---|---|
| **Dashboard Web UI** (`tools/asset_dashboard/`) | 視覺化瀏覽 pipeline 輸出、編輯 prompt、一鍵 Remake；適合所有使用者 |
| **CLI Orchestrator** (`pipeline/orchestrators/*.py`) | 可在終端機直接跑；支援 `--resume-from`、`--review-mode none` 批次模式；AI 透過 Bash 工具調用 |

兩者存取同一份 `art_source/manifest.json`，狀態完全一致。

### Spec / State / Sync

Asset 拆三層：**Spec**（意圖：kind / description / view / size）+ **State**（產物：PNG / spritesheet / .tscn）+ **Pixellab 上游**（rotation_urls / animations）。

| 動作 | API | CLI 等價 |
|---|---|---|
| 新建 | `POST /api/asset/create` | `orchestrator.py --name X --description ...` |
| 跑 stage | `POST /<type>/<name>/remake {stage}` | `orchestrator.py --name X --resume-from <stage>` |
| 改 spec + 跑 | `POST /<type>/<name>/remake {stage, overrides: {kind: "iso_building"}}` | `orchestrator.py --name X --kind iso_building --description ...` |
| 拉 Pixellab UI 編輯回本地 | `POST /character/<name>/sync {scope: "all"}` | （無 CLI 等價，0 credit） |

## Orchestrator 列表

| 檔案 | Pipeline | Stages |
|---|---|---|
| `orchestrators/autotile.py` | iso 地形 autotile | `generate_atlas` → `iso_project` → `verify_in_godot` → `import_to_godot` |
| `orchestrators/prop.py` | iso 建築 / 立面建築 / iso 小 prop | `generate_object` → `chroma_key` → `import_to_godot`（`--kind=iso_building\|building\|iso_prop`） |
| `orchestrators/npc_static.py` | 劇情靜態 NPC（4 向 idle） | `generate_4dir_base` → `add_idle_animation` → `compile_spritesheet` → `import_to_godot`（`--directions 4\|8`） |
| `orchestrators/npc_moving.py` | 移動 NPC / player（8 向 walk + 4 向 idle） | `generate_8dir_base` → `add_idle_animation` → `add_walk_animation` → `compile_spritesheet` → `import_to_godot` |

共用 CLI 旗標：
- `--review-mode {none,stage}` — 預設 `stage`（每階段停）
- `--resume-from <stage_name>` — 從某 stage 起跑
- `--force-restart-stage <stage_name>` — 強制重跑某已完成 stage（可多次）

範例：

```powershell
# 互動，每階段停
uv run python pipeline/orchestrators/npc_moving.py `
  --name chen_ayi --description "..." --review-mode stage

# 接續
uv run python pipeline/orchestrators/npc_moving.py `
  --name chen_ayi --resume-from add_walk_animation --review-mode stage

# 批次（一路跑完含自動匯入）
uv run python pipeline/orchestrators/npc_static.py `
  --name path_npc --description "..." --directions 4 --review-mode none
```

## 啟用步驟

### 1. 設定 token

複製 `.env.example` → `.env`，填入 `PIXELLAB_API_TOKEN`。各 orchestrator 啟動時會自動讀取，不需設系統環境變數。

### 2. 同步依賴

```powershell
uv sync
```

### 3. 啟動 Dashboard（可選）

```powershell
uv run uvicorn tools.asset_dashboard.backend.server:app --port 8765
```

開 http://localhost:8765/ 即可使用 Web UI。

## 輸出結構

```
art_source/                              # 所有美術資產（LFS 追蹤）
├── manifest.json                        # 所有資產索引
├── characters/<name>/
│   ├── rotations/{south,east,...}.png   # base 圖（Pixellab character_id reference）
│   └── spritesheet/
│       ├── <name>.png                   # 所有 idle/walk frames baked 進此檔
│       └── <name>.json                  # row 對照表（per (action,direction) 一 row）
├── tilesets/<name>/
│   ├── <name>_topdown.png
│   └── <name>_iso.png
└── objects/<name>/
    └── <name>.png

game/assets/textures/                    # import_to_godot 自動複製目的地
├── characters/<name>.{png,json}
├── tilesets/<name>.png
└── props/<name>.png
```

> 2026-05-12 起 animation frame 直接寫進 spritesheet，不再存 `animations/<action>/<dir>/frame_NNN.png` 中介檔。

## 重要限制

| 限制 | 影響 |
| --- | --- |
| Pixellab `/map-objects` 端點不支援 iso | 大建築改用 `--kind=iso_building`（走 `/create-image-pixflux` + `isometric:true`）；`/create-tileset` 仍需 PIL 投影才有 iso autotile |
| Mannequin template 強制角色 92×92 | size 參數是 hint 不是契約；下游 spritesheet 系統要適配 |
| Async 不可預測 | 標稱 ETA 180s 實測可能 30+ 分鐘；orchestrator 在每個 stage 結束後 exit(0) |
| API 回應 schema 部分欄位需試錯 | tileset / object 的 image_url 欄位可能變動 |

## 開發 / 測試

直接 CLI 呼叫底層函式（作 debug 用）：

```powershell
# 測試 token 載入
uv run python -c "import sys; sys.path.insert(0, 'pipeline'); from pixellab_client import load_token; print(load_token()[:8])"

# 測試 PIL 投影（需要既有 atlas）
uv run python -c "import sys; sys.path.insert(0, 'pipeline'); from post_process import project_atlas_file; from pathlib import Path; project_atlas_file(Path('input.png'), Path('output_iso.png'), 4, 4)"

# 看 manifest
uv run python -c "import sys; sys.path.insert(0, 'pipeline'); import manifest; import json; print(json.dumps(manifest.load(), indent=2, ensure_ascii=False))"
```
