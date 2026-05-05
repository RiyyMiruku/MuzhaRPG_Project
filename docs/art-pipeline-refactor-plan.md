# 美術生產 Pipeline 重構計畫

> 日期：2026-05-05　|　分支：`test-isometric-view`
> 狀態：執行中

把過去兩天的探索性腳本（pixflux + rotate + bitforge + animate + 自製 Wang atlas）整合成一條乾淨的、以 Pixellab 官方 MCP 為核心的美術生產 pipeline。

---

## 1. 各類美術素材的方法決策

### 1.1 Characters（玩家／NPC）

| 方法 | 評分 | 註記 |
| --- | --- | --- |
| pixflux 8 次獨立呼叫 | 5/10 | 同 seed 仍會飄、身份不一致 |
| bitforge style transfer | 4/10 | palette 一致但身份漂移更明顯 |
| pixflux + rotate × 7 + animate-with-text-v3 | 7/10 | 我們現行 pipeline，可用但 API 呼叫多 |
| **MCP `create_character` + `animate_character`** ⭐ | **9/10** | 1 call 出 8 方向 + character_id 持久化身份 |

**採用：MCP create_character + animate_character**

- 接受限制：view 只能 `low_top_down` / `high_top_down`，沒有真 iso（與既有 v1 endpoint 一樣）
- 接受限制：尺寸不嚴格（mannequin template 可能 92×92）
- 接受限制：async 生成 2-5 分鐘（甚至更久）

### 1.2 Autotiles（地形 Wang 16-tile set）

| 方法 | 評分 | 註記 |
| --- | --- | --- |
| pixflux 自製 4×4 atlas（Plan D） | 4/10 | 方形可，iso 不可，邊緣對位不精 |
| pixflux 16 張獨立 tile | 3/10 | 邊緣完全無法銜接 |
| MCP `create_isometric_tile`（單張） | 2/10 | 16 次呼叫 + 手動接邊，比上面更糟 |
| **MCP `create_topdown_tileset` + PIL 投影** ⭐ | **9/10** | 1 call 出 16 張 Wang，邊緣保證對齊；PIL 投影成 iso 已驗證 |

**採用：MCP create_topdown_tileset + project_to_iso.py**

### 1.3 Buildings / Props（map 物件）

| 方法 | 評分 | 註記 |
| --- | --- | --- |
| pixflux + iso prompt（現行） | 7/10 | 已產出 shophouse/temple/stall，品質可接受 |
| **MCP `create_map_object`** ⭐ | **8/10** | 為 prop 設計，原生透明背景，view 可選 |
| MCP `create_object`（8 向旋轉） | 6/10 | 對靜態建築過度設計 |

**採用：MCP create_map_object 為主；pixflux 保留為 fallback**

對於需要明顯 iso 視角的建築（屋頂尖角朝觀眾），create_map_object 的 high_top_down 可能不夠斜，視結果決定是否要 pixflux 補強。

### 1.4 Variations（同類 prop 的多種變體）

| 方法 | 評分 | 註記 |
| --- | --- | --- |
| 多次 create_map_object + 換 seed | 6/10 | 風格可能飄 |
| **MCP `vary_object`** ⭐ | **8/10** | 從現有 object 衍生，保持風格 |

**採用：先 create_map_object 一張代表，再用 vary_object 衍生變體**

---

## 2. 限制聲明（不被 MCP 解決的）

1. **真 isometric 視角不存在於任何 Pixellab 工具** — 所有 view 是 `low_top_down` / `high_top_down` / `side`。我們專案接受 high_top_down 已被測試圖證實夠用。
2. **角色尺寸與 mannequin template 綁定** — 大概率 92×92 而非請求的 64×64。下游 spritesheet 系統要適配這個尺寸。
3. **Async 不可預測** — 標稱 ETA 180s 實測可能超過 30 分鐘。所有工具必須假設長時等待 + 可中斷重試。

---

## 3. 新架構

### 3.1 目錄重命名

```
art_source/iso_pipeline/  →  art_source/pipeline/
```

`iso_pipeline` 現在誤導（並非全 iso、也並非只做 pipeline 一部分）。改名 `pipeline` 對應「美術生產 pipeline」的廣義意義。

### 3.2 檔案結構（最終版）

```
art_source/pipeline/
├── README.md                  # 入口文檔，工作流程總覽
├── mcp_server.py              # ⭐ 專案專屬 MCP server（FastMCP，stdio）
├── pixellab_client.py         # 底層 HTTP 客戶端（被 mcp_server 用，CLI fallback）
├── post_process.py            # PIL 後處理：chroma_key_bg, iso 投影 wrapper
├── manifest.py                # 讀寫 manifest.json（角色/物件/tileset 索引）
└── output/                    # 本地產出（gitignored 內容，僅保留結構）
    ├── manifest.json          # 所有產出的 metadata index
    ├── characters/<name>/     # 每個角色：rotations/, animations/, metadata.json
    ├── tilesets/<name>/       # 每組 autotile：top-down 原始 + iso 投影
    └── objects/<name>/        # 建築/prop：圖檔 + metadata
```

刪掉：
- `generate.py`、`generate_character.py`、`generate_character_with_ref.py` — 探索期腳本，已被 MCP 取代
- `generate_base.py`、`generate_rotations.py`、`generate_animations.py` — stage 腳本，邏輯併入 mcp_server
- `make_character.py` — orchestrator，preset 邏輯併入 mcp_server tool
- `test_endpoints.py` — 探索期，commit 進歷史就夠
- `MCP_SETUP.md` — 內容併入新 README

保留：
- `pixellab_client.py` — 改為**僅 HTTP 客戶端**，去掉所有 stage-specific 邏輯，作為 mcp_server 的後端
- `project_to_iso.py` — PIL 投影邏輯併入 `post_process.py`，原檔刪除

### 3.3 MCP Server 暴露的工具集

精選 8 個工具（涵蓋所有美術需求），使用 FastMCP（Python SDK）：

| Tool | 對應 Pixellab API | 我們的封裝重點 |
| --- | --- | --- |
| `create_character` | `/create-character-with-8-directions` | 預設 size=64, view=high_top_down, proportions=cartoon, 完成後自動下載 + 寫 manifest |
| `animate_character` | `/animate-character` | 從 manifest 查 character_id，等 jobs 完成，下載 frames |
| `get_character_status` | `/characters/{id}` | 看完成狀態 + 既有動畫 |
| `create_autotile` | `/create-topdown-tileset` | 預設 16×16 tile, 完成後自動跑 PIL 投影輸出 iso 版 |
| `create_building` | `/create-map-object` | 預設 high_top_down, 自動去背 + 寫 manifest |
| `create_prop_variants` | `/create-map-object` + `/vary-object` × N | 一次產主件 + N 個變體 |
| `list_assets` | （本地 manifest） | 列出所有已產出資產（不打 API） |
| `delete_asset` | `/characters/{id}` 等 | 同步刪除遠端 + 本地 + manifest |

### 3.4 Manifest 結構

`art_source/pipeline/output/manifest.json`：

```json
{
  "version": 1,
  "characters": {
    "chen_ayi": {
      "character_id": "uuid",
      "preset": "npc",
      "size": {"width": 92, "height": 92},
      "view": "high_top_down",
      "created_at": "2026-05-05T...",
      "rotations": ["south", "south-east", ...],
      "animations": {
        "idle": ["south", "north", "east", "west"],
        "walk": ["south", ...]
      },
      "local_path": "characters/chen_ayi/"
    }
  },
  "tilesets": { "market_grass_asphalt": {...} },
  "objects": { "muzha_shophouse": {...}, "bamboo_grove": {...} }
}
```

讓 `animate_character("chen_ayi", ...)` 可以用 name 查 character_id，使用者不需記 UUID。

### 3.5 .mcp.json 切 stdio

```json
{
  "mcpServers": {
    "muzharpg-pixellab": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "python", "art_source/pipeline/mcp_server.py"]
    }
  }
}
```

`uv run` 自動載入專案 venv + pyproject.toml；`mcp_server.py` 啟動時用 `python-dotenv` 讀 `.env` 拿 token。整條鏈不依賴系統環境變數。

刪除：
- `start-claude.ps1` — 不再需要 launcher
- 任何「需要設 PIXELLAB_API_TOKEN 進系統 env」的指引

---

## 4. 文檔更新

### 4.1 改寫
- `art_source/pipeline/README.md` — 新總覽，含完整工作流程（從 prompt 到 Godot scene）
- `docs/INDEX.md` — 加 pipeline 條目，更新 art_source/ 子節
- `art_source/characters/1-asset-creation.md` — 改成「老 4-向 top-down 流程，已 deprecated；新流程用 MCP」
- `art_source/characters/2-spritesheet-workflow.md` — 同上，新流程說明
- `game/assets/textures/environment/1-asset-creation.md` — 加上「使用 MCP create_autotile 取代手動 Pixellab Tilesets」段落
- `docs/scene-design-workflow.md` — 場景設計人入口，提到 MCP 工具

### 4.2 新增
- `art_source/pipeline/README.md`（新入口）
- `docs/art-pipeline-refactor-plan.md`（本文，留作 ADR）

### 4.3 刪除
- `art_source/iso_pipeline/MCP_SETUP.md` — 內容併入 README
- `start-claude.ps1` — 不再需要

---

## 5. 執行順序

1. ✅ 寫本計畫檔（這份）
2. 建 `art_source/pipeline/post_process.py`（chroma_key + iso 投影 + alpha utils）
3. 重構 `pixellab_client.py`（瘦身，純 HTTP）
4. 建 `art_source/pipeline/manifest.py`
5. 建 `art_source/pipeline/mcp_server.py`（FastMCP，8 個工具）
6. 切 `.mcp.json` 到 stdio
7. 端到端驗證：用新 MCP 工具產一個 NPC + 一張 autotile + 一棟建築
8. 確認運作後，刪除 `art_source/iso_pipeline/`、舊 `start-claude.ps1`、舊 stage 腳本
9. 更新所有文檔
10. Commit + push 分支

---

## 6. 不在這次重構範圍

- 真正切換到 iso 視角的 Godot 場景（`zone_iso_test.tscn` 之外）
- 把既有 4 個 zone（market/nccu/zhinan/riverside）轉換為 iso
- 動畫 frame → spritesheet 的 atlas 編譯（`scripts/generate_spritesheet.py` 已存在，預留接口即可）
- 對話／NPC 邏輯系統等與美術無關的部分

這些留待美術 pipeline 重構穩定後再進行。
