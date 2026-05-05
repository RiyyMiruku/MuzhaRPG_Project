# 美術生產 Pipeline

> 透過專案專屬 MCP Server 串接 Pixellab v2 API，產出角色、autotile、map 物件。所有資產由 [output/manifest.json](output/) 索引，使用者只需用「名字」操作。

## 架構

```
Claude Code
    │
    │  stdio (mcp protocol)
    ▼
mcp_server.py  ── FastMCP，暴露 8 個專案特化工具
    │
    ├── pixellab_client.py  ── Pixellab v1/v2 HTTP 端點封裝
    │       │
    │       │  HTTPS + Bearer token (從 .env 讀)
    │       ▼
    │     api.pixellab.ai
    │
    ├── post_process.py     ── PIL 後處理（去背、iso 投影）
    │
    └── manifest.py         ── output/manifest.json 索引
```

## 八個 MCP 工具

| 工具 | 功能 |
| --- | --- |
| `create_character(name, description, preset, view, proportions)` | 8 方向角色 sprite，後台 async 完成後自動下載 |
| `animate_character(name, action, directions, frame_count)` | 既有角色加動畫（idle / walk / 自訂），用 character_id 鎖身份 |
| `get_character_status(name)` | 查 manifest 中該角色狀態 |
| `create_autotile(name, lower, upper, transition_size, transition_description)` | 16-tile Wang autotile + 自動 PIL 投影成 iso 菱形 atlas |
| `create_building(name, description, width, height, view)` | 靜態建築/prop（map_object 端點，原生透明背景） |
| `list_assets(asset_type)` | 列出 manifest 所有資產 |
| `delete_asset(name, asset_type)` | 從 manifest 移除（不動本地檔/遠端資產） |

## 啟用步驟

### 1. 設定 token

複製 `.env.example` → `.env`，填入 `PIXELLAB_API_TOKEN`。`mcp_server.py` 啟動時會自動讀取，不需設系統環境變數。

### 2. 同步依賴

```powershell
uv sync
```

`pyproject.toml` 已包含 `mcp`、`requests`、`pillow`、`python-dotenv`。

### 3. 確認 .mcp.json

專案根 [.mcp.json](../../.mcp.json) 應為 stdio 設定：
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

### 4. 重啟 Claude Code

新 session 載入時自動啟動 server，工具會以 `mcp__muzharpg-pixellab__create_character` 等命名出現。

## 工作流程範例

### 建一個 NPC

```
（在 Claude Code 對話中）
"幫我建陳阿姨：中年市場攤販女性、紅花襯衫、米色圍裙，4 向 idle 即可"
→ Claude 呼叫:
   mcp__muzharpg-pixellab__create_character(
     name="chen_ayi",
     description="middle-aged taiwanese market vendor woman, ...",
     preset="npc",
     view="high_top_down",
     proportions="cartoon"
   )
→ 等 2-30 分鐘
→ 完成：output/characters/chen_ayi/rotations/{south,east,north,west,...}.png

"加 idle 動畫"
→ Claude 呼叫:
   mcp__muzharpg-pixellab__animate_character(
     name="chen_ayi", action="idle", directions=["south","east","north","west"], frame_count=4
   )
→ 完成：output/characters/chen_ayi/animations/idle/*/frame_*.png
```

### 建一張 autotile

```
"幫我建市場的 grass+asphalt autotile"
→ create_autotile(
    name="market_grass_asphalt",
    lower_description="green grass texture",
    upper_description="dark asphalt road",
    transition_size=0.25,
    transition_description="grey concrete curb"
  )
→ 完成：output/tilesets/market_grass_asphalt/
       ├─ market_grass_asphalt_topdown.png    (4×4 atlas, 64×64)
       └─ market_grass_asphalt_iso.png        (PIL 投影後菱形版, 128×64)
```

### 建建築 / prop

```
"幫我做木柵市場的紅磚街屋"
→ create_building(
    name="muzha_shophouse",
    description="traditional taiwanese two-story shophouse, red brick",
    width=128, height=128, view="high_top_down"
  )
→ output/objects/muzha_shophouse/muzha_shophouse.png
```

## 輸出結構

```
art_source/pipeline/output/        # gitignored 內容（PNG / JSON），結構保留
├── manifest.json                  # 所有資產索引
├── characters/<name>/
│   ├── rotations/{south,east,...}.png
│   └── animations/<action>/<dir>/frame_NNN.png
├── tilesets/<name>/
│   ├── <name>_topdown.png
│   └── <name>_iso.png
└── objects/<name>/
    └── <name>.png
```

## 重要限制

| 限制 | 影響 |
| --- | --- |
| Pixellab 沒有原生 isometric view | 用 `high_top_down`（~30°）+ PIL 投影 (autotile) 達近似效果 |
| Mannequin template 強制角色 92×92 | size 參數是 hint 不是契約；下游 spritesheet 系統要適配 |
| Async 不可預測 | 標稱 ETA 180s 實測可能 30+ 分鐘；server 用 30 分超時 |
| API 回應 schema 部分欄位需試錯 | tileset / object 的 image_url 欄位可能變動 |

## 為什麼不直接用官方 MCP（api.pixellab.ai/mcp）

評估過後選自寫 stdio server 而非用 HTTP 端點：

1. **Token 不需設系統環境變數** — stdio server 自己讀 .env
2. **工具集精簡** — 只暴露 8 個常用工具，不污染 Claude context（官方 28 個）
3. **內建專案慣例** — 預設 size、view、命名規則、輸出資料夾
4. **內建後處理** — 自動去背、iso 投影、寫 manifest

詳細決策：[docs/art-pipeline-refactor-plan.md](../../docs/art-pipeline-refactor-plan.md)

## 開發 / 測試

直接 CLI 呼叫底層函式（繞過 MCP，作 debug 用）：

```powershell
# 測試 token 載入
uv run python -c "import sys; sys.path.insert(0, 'art_source/pipeline'); from pixellab_client import load_token; print(load_token()[:8])"

# 測試 PIL 投影（需要既有 atlas）
uv run python -c "import sys; sys.path.insert(0, 'art_source/pipeline'); from post_process import project_atlas_file; from pathlib import Path; project_atlas_file(Path('input.png'), Path('output_iso.png'), 4, 4)"

# 看 manifest
uv run python -c "import sys; sys.path.insert(0, 'art_source/pipeline'); import manifest; import json; print(json.dumps(manifest.load(), indent=2, ensure_ascii=False))"
```
