---
name: art-pipeline
description: Use when the user wants to generate art assets (autotiles, props/buildings, NPC characters with directional sprites + animations) for this MuzhaRPG project. Triggers on requests like "幫我建一個 NPC", "make a character", "generate an autotile", "新增一個 prop", or any creation of pixel-art game assets via Pixellab. Skips for asking ABOUT the pipeline, debugging, or non-art work.
---

# 美術 Pipeline（CLI orchestrators）

本專案有 4 個 CLI orchestrator，將 Pixellab v2 API 包裝成分階段美術生成 pipeline。支援逐階段暫停 / 檢查 / 續跑，也支援無人值守的批次模式。

**兩種調用方式 —— 依情境選擇：**

1. **直接 CLI（透過 `Bash` 工具）** —— 互動模式、單一資產、想觀察每個 stage
2. **Dashboard job API（透過 HTTP）** —— 批次 / 多資產 / fire-and-forget；AI agent 不必掛機等待 Pixellab（單一資產約 10–30 分鐘）。詳見下方〈Dashboard job API 批次模式〉

`tools/asset_dashboard/` 是給人類用的主介面；同一個 backend 對外暴露 job API，最適合 AI 驅動的批次生成。

## 各 orchestrator 適用情境

| 需求 | Orchestrator | Pipeline |
|---|---|---|
| Iso 地形 autotile（Wang 16-tile + iso 投影） | `autotile.py` | `generate_atlas` → `iso_project` → `verify_in_godot` → `import_to_godot` |
| 大型建築（top-down ~30°） | `prop.py --kind=building` | `generate_object` → `chroma_key` → `import_to_godot` |
| 小型 iso prop（燈籠、攤車裝飾） | `prop.py --kind=iso_prop` | 同上，走 native iso 端點 → `import_to_godot` |
| 劇情靜態 NPC（idle 限定，**4 stages**） | `npc_static.py --directions 4 \| 8` | `generate_4dir_base` → `add_idle_animation` → `compile_spritesheet` → `import_to_godot` |
| 移動 NPC / 玩家（8 向 walk + 4 向 idle，**5 stages**） | `npc_moving.py` | `generate_8dir_base` → `add_idle_animation` → `add_walk_animation` → `compile_spritesheet` → `import_to_godot` |

`import_to_godot` 會自動完成 PNG/JSON 複製 + `.tscn` 生成 + manifest 更新，不需要再跑額外的匯入腳本。

## 命名規範

Asset name（manifest 鍵）由 regex 強制驗證。Orchestrator 在打 Pixellab 之前就會拒絕不合法的名稱。

```
^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$    length 3–64
```

建議命名結構：
- **具名 NPC**：`chen_ayi`、`lin_zhiwei`
- **泛用 NPC**：`vendor_market_01`、`student_nccu_03`
- **Tileset**：`market_grass_asphalt`、`riverside_water_sand`
- **建築**：`nccu_dormitory`、`market_shophouse_01`
- **Iso prop**：`lantern_red`、`cart_fruit`

每個 orchestrator 都建議帶 `--zone <z>`（`market|nccu|riverside|zhinan|shared|test` 其一）與 `--category <c>`（自由形，如 `vendor`、`decoration`），會寫成 `zone:<z>` / `category:<c>` tag 到 manifest。**名稱本身不要重複放 zone / category 資訊**。

## 共用 CLI flag

- `--name <key>` —— manifest 鍵（必填，須通過命名規範）
- `--zone {market,nccu,riverside,zhinan,shared,test}` —— tag
- `--category <free-form>` —— tag
- `--chapter <free-form>` —— tag（例：`1`、`prologue`）
- `--review-mode {none,stage}` —— 預設 `stage`（每階段停）；**批次 / 腳本模式必須用 `--review-mode none`**
- `--resume-from <stage_name>` —— 從指定 stage 起跑，前置 stage 由 manifest 讀
- `--force-restart-stage <name>` —— 強制重跑已完成的 stage（可多次）

### 角色專屬 flag
- `--description "..."` —— 角色外觀 prompt（首次必填，resume 時可省略）
- `--view {high_top_down,low_top_down,side}` —— 預設 `high_top_down`
- `--proportions {cartoon,chibi,stylized,realistic_male,realistic_female,heroic}` —— 預設 `cartoon`
- `--idle-frame-count N` —— 預設 4
- `--walk-frame-count N` —— 預設 8（僅 moving）
- `--directions {4,8}` —— 僅 `npc_static`；**4 = 永遠靜態，8 = 為未來升級保留**
- `--no-idle` —— 僅 `npc_static`；連 idle 都不要（純 rotation-only）
- `--only-directions south,east` —— **partial regen**，限定方向（僅 animation stage 生效）

### Tileset / Prop 專屬 flag
- `--lower "..."` + `--upper "..."` —— autotile 必填
- `--transition-size {0,0.25,0.5,1.0}` + `--transition-description "..."` —— autotile 可選
- `--kind {building|iso_prop}` —— `prop.py` 必填
- `--width N --height N`（building）/ `--size N`（iso_prop）
- `--collision {bottom_16x16,bottom_16x8,full,none}` —— `prop.py`
- `--no-collision` —— `prop.py` 略過碰撞 body

## 決策流程

```
1. 依使用者意圖從上表挑 orchestrator。
2. 批次 / 多個 asset / 不想掛機?
   → 是（預設應走這條）：用〈Dashboard job API 批次模式〉。
     - Dashboard backend 有跑時：curl POST /api/asset/create，每筆立即回 job_id
     - Dashboard backend 沒跑：先請使用者啟動，或退而求其次走 CLI for-loop
   → 否（單一 asset + 互動模式）：直接 Bash 調用 orchestrator
3. 首次 / Resume?
   → 首次：--description（autotile 是 --lower/--upper）必填
   → Resume：--resume-from <next_stage>，description 可省略（從 manifest 讀）
4. 是否要客製 idle / walk action_description?
   → 走 dashboard API：body 帶 idle_action_description / walk_action_description，backend 自動 pre-seed manifest
   → 走 CLI：啟動 orchestrator 前自行 set_prompt（見〈Pre-seed 動畫 prompt〉段落）
   → 不客製：預設只送 "idle"/"walk" 一個字給 Pixellab（頭轉 / 亂手機率高，不建議）
5. CLI 模式才需要選：--review-mode none（批次 / 腳本）vs --review-mode stage（跑完一階段停）
   API 模式恆為 --review-mode none（backend 寫死）
```

## Dashboard job API 批次模式（推薦 —— fire-and-forget）

**為什麼比 CLI for-loop 好：**
- Pixellab 單一角色 10–30 分鐘 → CLI for-loop 跑 5 個 NPC 要 1–2 小時，AI agent 一直掛機浪費 context
- Dashboard backend 的 `_jobs.start()` 用 `CREATE_NEW_PROCESS_GROUP`（Windows）/ `start_new_session`（POSIX）將 subprocess detach，不會被 uvicorn `--reload` 殺
- 每個 job 各自寫 log 到 `$TEMP/muzha_dashboard_<job_id>.log`
- 使用者可在 Web UI 看進度；AI agent 視需要 poll 或直接把 job_id 丟回給使用者

**前提**：dashboard backend 已啟動（`uv run uvicorn tools.asset_dashboard.backend.server:app --port 8765`）。沒跑時要先請使用者啟動，或直接 fallback 到 CLI 模式。

**API endpoint：**

| Endpoint | 用途 |
|---|---|
| `POST /api/asset/create` | 新建 asset，啟動完整 pipeline subprocess，立即回 `{job_id}` |
| `POST /api/asset/<type>/<name>/remake` | 重跑某 stage（支援 partial-direction），立即回 `{job_id}` |
| `GET /api/jobs` | 列出所有 job 狀態 |
| `GET /api/jobs/<job_id>` | 單一 job 詳情 + log tail |
| `DELETE /api/jobs/<job_id>` | 清掉已完成的 job 紀錄（RUNNING 拒絕刪） |

**`POST /api/asset/create` body 範例（character）：**
```json
{
  "asset_type": "character",
  "kind": "moving",                  // 或 "static"
  "name": "chen_ayi",
  "description": "middle-aged taiwanese market vendor woman, red floral shirt, beige apron",
  "zone": "market", "category": "vendor",
  "idle_frame_count": 4, "walk_frame_count": 8,
  "view": "high_top_down", "proportions": "cartoon",
  "idle_action_description": "...",  // 可選，客製 idle prompt
  "walk_action_description": "..."   // 可選，客製 walk prompt（僅 moving）
}
```

`idle_action_description` / `walk_action_description` 由 API 自動 pre-seed manifest（orchestrator 跑到對應 stage 會從 manifest 讀），**不需要**另外用 Python heredoc。

**Tileset / object** 用同一個 endpoint，換不同欄位：
- tileset：`asset_type=tileset`、`lower`、`upper`、`transition_size`、`transition_description`
- object：`asset_type=object`、`kind`（`iso_prop` | `building`）、`description`、`size` | `width`/`height`、`collision`

### 批次範例 —— 一次 queue 多個 NPC

```bash
# 1. 確認 backend 有跑
curl -s -f http://127.0.0.1:8765/api/manifest > /dev/null || {
  echo "dashboard not running, start it with: uv run uvicorn tools.asset_dashboard.backend.server:app --port 8765"
  exit 1
}

# 2. 一次 POST 多個（動畫 prompt 由 backend 自動 pre-seed）
DEFAULT_IDLE='standing in place, head perfectly still and facing forward, eyes straight ahead, no head turning, arms relaxed at sides with wrists hanging naturally and motionless, no random hand or wrist movement, gentle breathing only, posture consistent across all frames'
DEFAULT_WALK='walking forward in the direction the body is facing, head locked forward and aligned with torso, eyes fixed straight ahead, no head turning, no looking sideways, natural arm swing opposite to leg stride, consistent gait across all frames'

queue_npc() {
  local name="$1" kind="$2" desc="$3" zone="$4" category="$5"
  curl -s -X POST http://127.0.0.1:8765/api/asset/create \
    -H "Content-Type: application/json" \
    -d "$(jq -nc \
        --arg name "$name" --arg kind "$kind" --arg desc "$desc" \
        --arg zone "$zone" --arg cat "$category" \
        --arg idle "$DEFAULT_IDLE" --arg walk "$DEFAULT_WALK" \
        '{asset_type:"character", kind:$kind, name:$name, description:$desc,
          zone:$zone, category:$cat,
          idle_action_description:$idle,
          walk_action_description: (if $kind=="moving" then $walk else null end)}')"
  echo
}

queue_npc vendor_market_01 static "elderly fruit seller, straw hat, beige apron" market vendor
queue_npc vendor_market_02 static "young bubble tea shop owner, ponytail, white t-shirt with logo" market vendor
queue_npc chen_ayi         moving "middle-aged taiwanese market vendor woman, red floral shirt, beige apron" market vendor
```

→ Backend 立即回三個 `{"job_id": "abc123...", "asset_name": "..."}`，detached subprocess 跑起來。Agent 把 job_id 收集後回報給使用者，**不必等任一筆跑完**。

### 檢查狀態（視需要）

```bash
curl -s http://127.0.0.1:8765/api/jobs | jq '.jobs[] | {asset_name, stage, status, exit_code}'
```

或抓單一 job 的 log tail：
```bash
curl -s "http://127.0.0.1:8765/api/jobs/<job_id>?tail=80"
```

**Status 值**：`pending` / `running` / `completed` / `failed`（exit_code 為 0 才算 `completed`）

### Partial regen 走同一條 API

```bash
curl -s -X POST http://127.0.0.1:8765/api/asset/character/chen_ayi/remake \
  -H "Content-Type: application/json" \
  -d '{"stage": "add_walk_animation", "directions": ["east","north-east"]}'
```

→ Backend 啟動 `--resume-from add_walk_animation --force-restart-stage add_walk_animation --only-directions east,north-east` 的 subprocess，立即回 `job_id`。

### 何時 fallback 到 CLI 模式

- Dashboard 沒跑（`curl /api/manifest` 失敗）且使用者不打算啟動
- 一次性測試 / 不想留 manifest 紀錄就跑壞
- 使用者明確說「用 CLI」/「不要走 dashboard」

其他情況一律優先用 API。

## Pre-seed 動畫 prompt（重要 —— 直接 CLI 才需要）

Orchestrator 本身**沒有** `--idle-action-description` / `--walk-action-description` 這類 CLI flag。客製 idle / walk 提示詞的唯一方式：**在啟動 orchestrator 之前**先把 prompt 寫入 manifest，orchestrator 跑到對應 stage 時會從 manifest 讀。

Web UI 的 Create modal 會自動做這件事；CLI / 腳本要自己做。

模板（Python helper 包在 bash heredoc 裡）：

```bash
uv run python - <<'PY'
import sys; sys.path.insert(0, "pipeline")
import manifest
NAME = "chen_ayi"          # 目標角色
IDLE = (
  "standing in place, head held perfectly still and facing forward in the "
  "same direction as the torso, eyes looking straight ahead, no head turning, "
  "arms relaxed at sides with wrists hanging naturally and motionless — no "
  "random hand or wrist movement, no finger fidgeting, gentle breathing only, "
  "feet planted, posture consistent across all frames"
)
WALK = (
  "walking forward in the same direction the body is facing, head locked "
  "forward and aligned with torso, eyes fixed straight ahead in the walking "
  "direction, no head turning, no looking sideways, natural arm swing opposite "
  "to leg stride, consistent gait and posture across all frames"
)
# 先建一個 manifest stub（orchestrator 看到 entry 已存在會 merge，不會覆蓋）
manifest.upsert_character(name=NAME, fields={"status": "init"})
manifest.set_prompt("character", NAME, "add_idle_animation", IDLE)
manifest.set_prompt("character", NAME, "add_walk_animation", WALK)   # 僅 moving 需要
print("seeded prompts for", NAME)
PY
```

這份 default prompt 是專門對付 Pixellab v3 mode 容易出現的「頭轉 / 亂甩手」問題，搭配 `submit_character_animation` 已寫死的 `text_guidance_scale=12.0`（比官方預設 8 嚴格）。**所有新 NPC 都建議用這份 prompt 為基底**，只在角色需要明顯不同的姿態時才客製。

## 範例

### 單一新角色（互動模式，使用者要檢查每階段）

```bash
uv run python pipeline/orchestrators/npc_moving.py \
  --name chen_ayi \
  --description "middle-aged taiwanese market vendor woman, red floral shirt, beige apron" \
  --zone market --category vendor \
  --review-mode stage
```

→ 跑完 `generate_8dir_base` 後停。給使用者看 `art_source/characters/chen_ayi/rotations/*.png`。確認 OK 後：

```bash
uv run python pipeline/orchestrators/npc_moving.py \
  --name chen_ayi --resume-from add_idle_animation
```

### 批次模式（CLI fallback —— dashboard 沒跑時才用）

> 優先用 dashboard job API（上方段落）；這條 for-loop 只在 backend 不可用時 fallback。

```bash
# 先 pre-seed 所有要客製的 prompt（見〈Pre-seed 動畫 prompt〉段落）

# 然後一次跑完（--review-mode none = 不在 stage 之間停）
for NAME_DESC in \
  "vendor_market_01:elderly fruit seller, straw hat, beige apron" \
  "student_nccu_02:university student, casual hoodie, backpack" \
  "monk_zhinan_01:elderly buddhist monk, grey robe, prayer beads"; do
  NAME="${NAME_DESC%%:*}"
  DESC="${NAME_DESC#*:}"
  uv run python pipeline/orchestrators/npc_static.py \
    --name "$NAME" --description "$DESC" \
    --zone market --category vendor \
    --directions 4 --review-mode none
done
```

CLI for-loop 的 trap（走 dashboard API 都不會遇到）：
- AI agent 用 `Bash` 跑這段 for-loop 會**阻塞**到全部跑完才回 → 5 個 NPC 可能 1–2 小時
- 解法 a：每個指令尾巴加 `&` 背景化 + `wait`，但 Bash tool 對背景 process 行為複雜，容易踩雷
- 解法 b：用 `Bash` 的 `run_in_background: true` 跑整段 for-loop，agent 立刻回；但失敗只能事後看 log，沒 Web UI 那麼方便
- **真正想 fire-and-forget，請使用者啟動 dashboard 就好**

### Partial regen —— 只重生壞掉的方向

```bash
# 例：chen_ayi 的 walk_east 與 walk_north-east 頭轉嚴重，只重生這兩個方向
uv run python pipeline/orchestrators/npc_moving.py \
  --name chen_ayi \
  --resume-from add_walk_animation \
  --force-restart-stage add_walk_animation \
  --only-directions east,north-east \
  --review-mode none
```

`--only-directions` 的效果：
1. 只把那兩個方向送 Pixellab（省 6 個方向的 credit）
2. `compile_spritesheet` 自動 patch 對應 row（不重組整張 sheet）
3. `import_to_godot` 整張複製到 Godot 端（秒級）

合法方向值：`south, east, north, west, south-east, north-east, north-west, south-west`。

idle 僅 4 cardinal（south/east/north/west）；walk 全 8。orchestrator 自動取交集。

### Iso autotile / Building / Iso prop

```bash
# Autotile
uv run python pipeline/orchestrators/autotile.py \
  --name market_grass_asphalt \
  --lower "green grass texture" --upper "dark asphalt road" \
  --zone market --category terrain \
  --transition-size 0.25 --transition-description "grey concrete curb" \
  --review-mode none

# 大型建築（high_top_down，不投影）
uv run python pipeline/orchestrators/prop.py \
  --name market_shophouse_01 --kind building \
  --description "traditional taiwanese two-story shophouse, red brick" \
  --zone market --category building \
  --width 128 --height 128 \
  --review-mode none

# 小型 iso 單格 prop
uv run python pipeline/orchestrators/prop.py \
  --name lantern_red --kind iso_prop \
  --description "red paper lantern with gold tassel" \
  --zone market --category decoration --size 32 \
  --review-mode none
```

## 重要限制（不要違反）

- **`directions=4` 與 `directions=8` 是不同 character_id**，Pixellab 後端不通用。一旦選 4，日後想加 walk 動畫必須**重新生成整隻角色**。預設 8 是安全選擇；只有在使用者明確說「絕對不會動」才用 4。
- **`create_building` 不做 PIL iso 投影**。建築立體感不能被 affine 壓扁；接受 `high_top_down` ~30° 視角。
- **生成是 async 且不可預測**。標稱 ETA 180s 但實測可能 10–30 分鐘。`--review-mode stage` 跑完一個 stage 就 `sys.exit(0)`，不會 hang。
- **首次跑必須給 `--description`**（autotile 是 `--lower` / `--upper`）。Resume 時可省略，會從 manifest 讀。
- **不要直接呼叫底層 `pixellab_client` 函式**來重複實作 pipeline 邏輯。orchestrator 已封裝好；只需 Bash 調用（例外：上面的 pre-seed prompts 用 `pipeline.manifest` API 是 OK 的，因為那只是 manifest CRUD）。
- **動畫 frame 不再存單張 PNG**。Pixellab 回傳的 frame 直接 paste 進 `spritesheet/<name>.png`（refactor 後行為）。本地不會有 `animations/<action>/<direction>/frame_*.png`。

## 產出位置（refactor 後）

```
art_source/
├── manifest.json                   ← 單一索引，用 --name 查
├── characters/<name>/
│   ├── rotations/                  ← 4 或 8 張 base 圖（Pixellab character_id reference）
│   │   ├── south.png, east.png, ...
│   └── spritesheet/                ← 動畫 single source of truth
│       ├── <name>.png              ← 所有 idle/walk frames 都 baked 進此檔
│       └── <name>.json             ← row 對照表（每個 (action, direction) 一 row）
├── tilesets/<name>/
│   ├── <name>_topdown.png          ← Pixellab 原始 Wang atlas
│   └── <name>_iso.png              ← iso_project 後給 TileMapDual addon 用
└── objects/<name>/<name>.png

game/assets/textures/               ← import_to_godot 自動複製目的地
├── characters/<name>.{png,json}    ← 從 spritesheet/ 複製
├── tilesets/<name>.png             ← 從 <name>_iso.png 複製
└── props/<name>.png                ← 從 objects/<name>.png 複製
```

## 延伸閱讀

- Stage 之間依賴 / 設計理由：`docs/archive/2026-05-art-pipeline-design-spec.md`
- Pipeline 整體架構：`pipeline/README.md`
- 底層 Pixellab API wrapper：`pipeline/pixellab_client.py`（注意：動畫端點預設 `text_guidance_scale=12.0`，比 Pixellab 官方 8 嚴，為了減少頭轉 / 亂手）
- Spritesheet 寫入 API（3 個 function）：`pipeline/spritesheet.py`（`load_or_init_sheet` / `write_animation_frames` / `save_sheet`）
- Web UI 主介面：啟動 `tools/asset_dashboard/`（`uv run uvicorn tools.asset_dashboard.backend.server:app --port 8765`），打開 http://localhost:8765/ —— 對單一 asset 的視覺化檢視 + 編輯 prompt + per-direction Remake 比 CLI 順
