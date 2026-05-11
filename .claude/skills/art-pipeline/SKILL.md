---
name: art-pipeline
description: Use when the user wants to generate art assets (autotiles, props/buildings, NPC characters with directional sprites + animations) for this MuzhaRPG project. Triggers on requests like "幫我建一個 NPC", "make a character", "generate an autotile", "新增一個 prop", or any creation of pixel-art game assets via Pixellab. Skips for asking ABOUT the pipeline, debugging, or non-art work.
---

# Art Pipeline (CLI Orchestrators)

This project has 4 CLI orchestrators that wrap Pixellab's v2 API into stage-by-stage art-generation pipelines. They support pause/review/resume so the human can check intermediate output before continuing, and a batch mode for unattended runs.

**You invoke them via the `Bash` tool.**

## When to use which orchestrator

| Need | Orchestrator | Pipeline |
|---|---|---|
| Iso 地形 autotile (Wang 16-tile + iso 投影) | `autotile.py` | `generate_atlas` → `iso_project` → `verify_in_godot` → `import_to_godot` |
| 大建築 (top-down ~30°) | `prop.py --kind=building` | `generate_object` → `chroma_key` → `import_to_godot` |
| 小型 iso prop (燈籠、攤車裝飾) | `prop.py --kind=iso_prop` | 同上,但走 native iso 端點 → `import_to_godot` |
| 劇情靜態 NPC (4 向 idle,不會移動) | `npc_static.py --directions 4` | `generate_4dir_base` → `add_idle_animation` → `compile_spritesheet` → `import_to_godot` |
| 可能會升級成移動 NPC 的角色 | `npc_static.py` (預設 `--directions 8`) | 同上但生 8 方向,日後加 walk 不用重生 → `import_to_godot` |
| 移動 NPC / player (8 向 walk + 4 向 idle) | `npc_moving.py` | `generate_8dir_base` → `add_idle_animation` → `add_walk_animation` → `compile_spritesheet` → `import_to_godot` |

`import_to_godot` 是所有 orchestrator 的最後一個 stage，自動完成 PNG 複製 + `.tscn` 生成 + manifest 更新，不需要再跑額外的匯入腳本。`--review-mode stage` 會在 `import_to_godot` 之前停下讓人檢查中間產物。

## Naming convention

Asset names (manifest keys) are regex-enforced. Orchestrators reject invalid
names before any Pixellab call.

```
^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$    length 3–64
```

Recommended structures:
- **Named NPC**: `chen_ayi`, `lin_zhiwei`
- **Generic NPC**: `vendor_market_01`, `student_nccu_03`
- **Tilesets**: `market_grass_asphalt`, `riverside_water_sand`
- **Buildings**: `nccu_dormitory`, `market_shophouse_01`
- **Iso props**: `lantern_red`, `cart_fruit`

Use `--zone <z>` (one of `market|nccu|riverside|zhinan|shared|test`) and
`--category <c>` (free-form, e.g. `vendor`, `decoration`) on every orchestrator
to write `zone:<z>` / `category:<c>` tags into the manifest. Do NOT duplicate
zone/category info inside the name itself.

Filter via `art_source/pipeline/orchestrators/list_assets.py` (e.g.
`--zone market --type character`). Full detail: `docs/asset-naming-convention.md`.

## Common CLI flags (all orchestrators)

- `--name <key>` — manifest 鍵 (必填,須通過命名規範)
- `--zone {market,nccu,riverside,zhinan,shared,test}` — 寫入 `zone:<z>` tag
- `--category <free-form>` — 寫入 `category:<c>` tag
- `--review-mode {none,stage}` — 預設 `stage` (每階段停,包含在 `import_to_godot` 前停);`none` = 一路跑完含自動匯入
- `--resume-from <stage_name>` — 從某 stage 起跑,前面 stage 由 manifest 讀已完成路徑
- `--force-restart-stage <name>` — 強制重跑某已完成 stage (可多次)
- `--collision <preset>` — (prop.py) 碰撞 preset (e.g. `full`, `bottom_half`, `none`)
- `--no-collision` — (prop.py) 略過碰撞 body 生成

## Decision flow

```
1. Read user's request → pick orchestrator from table above
2. First time generating this asset?
   → Yes: include --description (and --lower/--upper for autotile)
   → No (resume): use --resume-from <next_stage>, omit --description (read from manifest)
3. Default to --review-mode stage so user can check each stage's output
   → User explicitly says "一路跑完" / "批次" / "別問我" → --review-mode none
4. Run via Bash tool. After stage completes, the orchestrator prints the output path and exits 0.
   Show the user the path; ask if it looks good before resuming.
```

## Examples

**新建一個會走路的 NPC (對話):**
```powershell
uv run python art_source/pipeline/orchestrators/npc_moving.py `
  --name chen_ayi `
  --description "middle-aged taiwanese market vendor woman, red floral shirt, beige apron" `
  --zone market --category vendor `
  --review-mode stage
```
→ 跑完 `generate_8dir_base` 後停（`--review-mode stage` 在每個 stage 結束後停，含 `import_to_godot` 前）。給使用者看 `output/characters/chen_ayi/rotations/*.png`。確認 OK 後:
```powershell
uv run python art_source/pipeline/orchestrators/npc_moving.py `
  --name chen_ayi --resume-from add_idle_animation
```

**確認絕對不會移動的劇情背景 NPC (省 credit):**
```powershell
uv run python art_source/pipeline/orchestrators/npc_static.py `
  --name vendor_market_01 `
  --description "elderly fruit seller, straw hat" `
  --zone market --category vendor `
  --directions 4 --review-mode none
```

**Iso autotile:**
```powershell
uv run python art_source/pipeline/orchestrators/autotile.py `
  --name market_grass_asphalt `
  --lower "green grass texture" --upper "dark asphalt road" `
  --zone market --category terrain `
  --transition-size 0.25 --transition-description "grey concrete curb"
```

**大建築 (high_top_down,不投影):**
```powershell
uv run python art_source/pipeline/orchestrators/prop.py `
  --name market_shophouse_01 --kind building `
  --description "traditional taiwanese two-story shophouse, red brick" `
  --zone market --category building `
  --width 128 --height 128
```

**小型 iso 單格 prop:**
```powershell
uv run python art_source/pipeline/orchestrators/prop.py `
  --name lantern_red --kind iso_prop `
  --description "red paper lantern with gold tassel" `
  --zone market --category decoration --size 32
```

## Important constraints (don't violate)

- **`directions=4` 與 `directions=8` 是不同 character_id**,Pixellab 後端不通用。一旦選 4,日後想加 walk 動畫須**重新生成整隻角色**。預設 8 是安全選擇;只在使用者明確說「絕對不會動」才用 4。
- **`create_building` 不做 PIL iso 投影**。建築立體感不能被 affine 壓扁;接受 `high_top_down` ~30° 視角。
- **生成是 async 且不可預測**。標稱 ETA 180s 但實測可能 10-30 分鐘。`--review-mode stage` 跑完一個 stage 就 `sys.exit(0)`,不會 hang。
- **第一次跑必須給 `--description`** (`autotile` 是 `--lower`/`--upper`)。Resume 時可省略 — 從 manifest 讀。
- **不要直接呼叫底層 `pixellab_client` 函式**來重複實作 pipeline 邏輯。orchestrator 已封裝好;只需 Bash 調用。

## Output locations

```
art_source/pipeline/output/
├── manifest.json                    ← 單一索引,用 `--name` 查
├── characters/<name>/
│   ├── rotations/{south,east,...}.png
│   ├── animations/{idle,walk}/<dir>/frame_NNN.png
│   └── spritesheet/  (compile_spritesheet 階段產出)
├── tilesets/<name>/
│   ├── <name>_topdown.png
│   └── <name>_iso.png               ← 給 TileMapDual addon 用
└── objects/<name>/<name>.png
```

## Where to escalate

- 想看 stage 之間的依賴 / 設計理由:`docs/superpowers/specs/2026-05-05-art-pipeline-orchestrators-design.md`
- 想看完整實作步驟:`docs/superpowers/plans/2026-05-05-art-pipeline-orchestrators.md`
- pipeline 整體架構:`art_source/pipeline/README.md`
- 底層 pixellab API wrapper:`art_source/pipeline/pixellab_client.py`
- 視覺化檢視 + 編輯 prompt + Remake:啟動 `tools/asset_dashboard/`(`uv run uvicorn tools.asset_dashboard.backend.server:app --port 8765`),開 http://localhost:8765/。
