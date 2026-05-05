# Art Pipeline Orchestrators — 設計文件

> 日期:2026-05-05  |  分支:`test-isometric-view`  |  狀態:設計已核可,待寫實作計畫

把現有 `art_source/pipeline/` 的 MCP 工具集擴成 4 條可批次、可分階段、可中斷續跑的 CLI orchestrator,以支援 ISOMETRIC 視角遊戲架構升級。

---

## 1. 動機

現況([art_source/pipeline/mcp_server.py](../../../art_source/pipeline/mcp_server.py))把每條美術生產鏈封裝成一個 MCP 工具(`create_character`、`create_autotile`、`create_building`)。這對單張互動式生成 OK,但有三個缺口:

1. **無中途檢視點** — 一個 MCP 呼叫 = 一條黑盒。NPC 動畫鏈可耗 30+ 分鐘,中途出錯只能整批重跑。
2. **無批次 / 續跑** — 想一次生成 10 個 NPC、或從某 stage 接續(例如「base sprite 已通過,只跑 walk 動畫」),目前做不到。
3. **死碼累積** — `pixellab_client.py` 內 `call_pixflux` / `call_rotate` / `call_animate_with_text_v3` 已被 v2 端點取代,refactor plan 已宣告淘汰但未刪。

同時,評估 4 條目標 pipeline(iso autotile / iso prop / 靜態 NPC / 移動 NPC)時也發現:

- Pipeline 2(props)在 Pixellab API **沒有原生 iso 端點**(`create-map-object` 只有 top_down/high_top_down/side);`create-isometric-tile` 適合單格小物但不適合大建築。
- Pipeline 3(靜態 4 向 NPC)目前強制走 8-dir 端點,浪費 ~50% credit;但 4-dir 與 8-dir 是不同 character_id,直接切會失去身份升級彈性。

---

## 2. 範圍

### 在範圍內

- 新增 `art_source/pipeline/orchestrators/` 子目錄,含 4 條 CLI 腳本與共用 stage 框架
- MCP 層最小變更:`create_character` 加 `directions` 參數、新增 `create_iso_prop` 工具、補 `submit_character_4dir`
- 刪除已宣告淘汰的 v1 死碼
- 更新 [art_source/pipeline/README.md](../../../art_source/pipeline/README.md) 與 [docs/INDEX.md](../../INDEX.md)

### 不在範圍

- 不改 Godot 端 importer / SpriteSheetLoader / TileMapDual 設定
- 不改 [scripts/generate_spritesheet.py](../../../scripts/generate_spritesheet.py)(orchestrator 用 subprocess 呼叫)
- 不寫 GUI / TUI 預覽器(stage 暫停時只印路徑,使用者用 IDE 看圖)
- 不做 Pixellab 後端資產刪除
- 不改 4 個既有 zone(market/nccu/zhinan/riverside)的 iso 化

---

## 3. 各 Pipeline 對 ISO 視角的支援度

| Pipeline | 視角需求 | Pixellab 原生支援 | 採取策略 |
|---|---|---|---|
| 1. Autotile | iso 菱形 | 無;但 `create-topdown-tileset` + PIL 2:1 affine 投影已驗證(TileMapDual addon 吃菱形 atlas) | 維持現狀:`create_autotile` 同時輸出 `_topdown.png` + `_iso.png` |
| 2. Prop | iso(大建築 + 小物) | 大建築:無原生 iso,只有 `high_top_down`(~30°);小單格:`create-isometric-tile` 有原生 iso | 拆兩個工具:大建築走 `create_building`(`high_top_down` + prompt),小物走新 `create_iso_prop`(`create-isometric-tile`)。**不對 building 做 PIL 投影**,因 affine 會壓扁立體感 |
| 3. 靜態 NPC | top-down 4 向 idle | 4-dir 與 8-dir 是不同端點,character_id 互不通用 | `create_character` 加 `directions: int = 8` 參數,預設 8(保留升級彈性),允許傳 4(劇情背景路人省 credit) |
| 4. 移動 NPC | top-down 8 向 walk + 4 向 idle | 完整支援(`create-character-with-8-directions` + `animate-character`) | 維持現有 API 路徑,封裝成 orchestrator |

---

## 4. 架構

### 4.1 目錄

```
art_source/pipeline/
├── mcp_server.py              (微調:加 directions 參數、加 create_iso_prop)
├── pixellab_client.py         (補 submit_character_4dir;刪 v1 死碼)
├── post_process.py            (不變)
├── manifest.py                (擴 stages 欄位)
└── orchestrators/             ⭐ 新
    ├── __init__.py
    ├── _common.py             ← stage 框架 + CLI 共用 args
    ├── autotile.py            ← Pipeline 1
    ├── prop.py                ← Pipeline 2(--kind=building|iso_prop)
    ├── npc_static.py          ← Pipeline 3
    └── npc_moving.py          ← Pipeline 4
```

### 4.2 Stage 框架(`_common.py`)

提供:

- **`@stage(name: str)`** 裝飾器 — 包裝階段函式,自動處理 manifest stages 寫入、resume skip、review-mode break
- **`parse_common_args()`** — 統一 CLI 參數
  - `--name`(必填)
  - `--review-mode {none, stage, step}`(預設 `stage`)
  - `--resume-from <stage_name>`(從某 stage 起跑,前面 stage 跳過但讀取已存路徑)
  - `--description`、`--directions` 等 pipeline 特有參數
- **`StageContext`** dataclass — 跨 stage 傳遞狀態(name、manifest entry、token、output_dir)

行為合約:

| review-mode | stage 完成時 | step(每 API 呼叫) |
|---|---|---|
| `none` | 寫 manifest,繼續下一 stage | 不停 |
| `stage` | 寫 manifest,印 stage 名與產物路徑,`sys.exit(0)` | 不停 |
| `step` | 同 stage | 每個 API 呼叫後印路徑、`sys.exit(0)` |

`--resume-from` 從指定 stage 起跑;前面 stage 由 manifest 讀回路徑,不重打 API。

### 4.3 Manifest 擴充

現有 manifest entry 加 `stages` 欄位:

```json
{
  "characters": {
    "chen_ayi": {
      "character_id": "uuid",
      "preset": "npc",
      "directions": 4,
      "stages": {
        "generate_4dir_base": {
          "completed_at": "2026-05-05T10:30:00",
          "paths": ["output/characters/chen_ayi/rotations/south.png", ...]
        },
        "add_idle_animation": {"completed_at": "...", "paths": [...]},
        "compile_spritesheet": {"completed_at": "...", "paths": [...]}
      },
      ...
    }
  }
}
```

`manifest.py` 加 `mark_stage(asset_type, name, stage_name, paths)` 與 `get_completed_stages(asset_type, name)`。

### 4.4 各 orchestrator 的 stage 切分

#### `autotile.py`

| Stage | 動作 | API 呼叫 |
|---|---|---|
| `generate_atlas` | `create-topdown-tileset` 取 4×4 atlas | 1 次 async |
| `iso_project` | PIL 投影成菱形 | 0(本地) |
| `verify_in_godot` | 印 Godot import 提示 + path,**不做事** | 0 |

#### `prop.py`(`--kind=building` 或 `--kind=iso_prop`)

| Stage | 動作 |
|---|---|
| `generate_object` | building → `create-map-object`;iso_prop → `create-isometric-tile` |
| `chroma_key` | PIL 去背(若需要) |
| `compile_variants`(可選,`--variants N`) | `vary-object` × N |

#### `npc_static.py`

| Stage | 動作 |
|---|---|
| `generate_4dir_base` | `create-character-with-4-directions`(若 `--directions 8` 則走 8-dir) |
| `add_idle_animation`(預設啟用,可 `--no-idle` 關) | `animate-character`,4 向 idle |
| `compile_spritesheet` | subprocess 呼叫 `scripts/generate_spritesheet.py` |

#### `npc_moving.py`

| Stage | 動作 |
|---|---|
| `generate_8dir_base` | `create-character-with-8-directions` |
| `add_idle_animation` | `animate-character`,4 向 idle |
| `add_walk_animation` | `animate-character`,8 向 walk |
| `compile_spritesheet` | subprocess 呼叫 `scripts/generate_spritesheet.py` |

### 4.5 MCP 層變更(最小)

1. **`pixellab_client.py`**
   - 新增 `submit_character_4dir(...)` — wrapper around `CREATE_CHAR_4DIR_URL`(URL 已 import)
   - 刪除 `call_pixflux`、`call_rotate`、`call_animate_with_text_v3`(v1 死碼)
   - 同步刪除對應 URL 常數(`PIXFLUX_URL`、`ROTATE_URL`、`ANIMATE_TEXT_V3_URL`)

2. **`mcp_server.py`**
   - `create_character` 加 `directions: int = 8` 參數,內部分派到 8-dir 或 4-dir submit
   - 新增 `create_iso_prop(name, description, size)` 工具,包 `create-isometric-tile` 端點

3. **`pixellab_client.py`** 再補 `submit_iso_tile()`(因要新工具)

---

## 5. CLI 使用範例

對話中 AI 透過 Bash 呼叫:

```powershell
# 互動模式 — 每 stage 停一次
uv run python art_source/pipeline/orchestrators/npc_moving.py `
  --name chen_ayi `
  --description "middle-aged taiwanese market vendor woman, red floral shirt, beige apron" `
  --review-mode stage

# 看完 base 沒問題 → 接續
uv run python art_source/pipeline/orchestrators/npc_moving.py `
  --name chen_ayi --resume-from add_idle_animation --review-mode stage

# 批次模式 — 一路跑完
uv run python art_source/pipeline/orchestrators/npc_static.py `
  --name shopkeeper_li --description "..." --directions 4 --review-mode none
```

---

## 6. 資料流

```
使用者(對話)
    │
    │  自然語言:"幫我建陳阿姨,中年市場攤販女性..."
    ▼
Claude(AI agent)
    │
    │  Bash 工具
    ▼
orchestrators/npc_moving.py  ──→  manifest.py(讀已完成 stage)
    │
    │  逐 stage 執行:
    │
    ├── generate_8dir_base    ──→  pixellab_client.submit_character_8dir
    ├── add_idle_animation    ──→  pixellab_client.submit_character_animation
    ├── add_walk_animation    ──→  pixellab_client.submit_character_animation
    └── compile_spritesheet   ──→  subprocess: scripts/generate_spritesheet.py
                                       │
                                       ▼
                                output/characters/chen_ayi/spritesheet/
```

---

## 7. 錯誤處理 / 邊界

- **API 5xx 重試**:已在 `pixellab_client._post` 處理(4 次 exp backoff),orchestrator 直接 propagate
- **超時**:Pixellab async 超過 30 分視為失敗,orchestrator 寫 manifest `stages.<name>.error = "timeout"` 後 `sys.exit(1)`,使用者可直接 `--resume-from <stage>` 再試
- **`--resume-from` 指向未存在 stage**:報錯列出可用 stage 名
- **manifest 內 stage 已完成但檔案不見**:警告但繼續(信任 manifest;若要重跑用 `--force-restart-stage <name>`)
- **`directions=4` 後想升級成移動 NPC**:文件明示「需重新 `create_character`,character_id 不通用」;不寫自動升級邏輯(會誤導)

---

## 8. 測試策略

每個 orchestrator 寫一個 smoke test:

- 使用 `--review-mode none` 跑一次完整流程(用便宜的 prompt)
- 驗證 manifest stages 全寫入
- 驗證輸出檔案結構符合 [art_source/pipeline/README.md](../../../art_source/pipeline/README.md) 約定的路徑

`_common.py` 的 stage 框架單元測試:

- `@stage` 裝飾器在不同 review-mode 下的行為
- `--resume-from` 跳過已完成 stage
- manifest stage 寫入冪等

---

## 9. 文件更新

- [art_source/pipeline/README.md](../../../art_source/pipeline/README.md) — 加 orchestrators 區塊,標 MCP 與 CLI 兩種用法的差異
- [docs/INDEX.md](../../INDEX.md) — 新增本 spec 連結 + orchestrator 用途說明
- 不寫獨立 orchestrator README(README.md 一份統包)

---

## 10. 不影響的部分

- Godot 端美術載入:依然用 [SpriteSheetLoader](../../../game/scripts/sprite_sheet_loader.gd)、TileMapDual addon
- 既有 4 zone(market/nccu/zhinan/riverside)維持 top-down,iso 化是另一條工作分支
- 對話、NPC 行為等非美術系統
