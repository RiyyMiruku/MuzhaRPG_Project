---
name: art-pipeline
description: Use when the user wants to generate art assets (autotiles, props/buildings, NPC characters with directional sprites + animations) for this MuzhaRPG project. Triggers on requests like "幫我建一個 NPC", "make a character", "generate an autotile", "新增一個 prop", or any creation of pixel-art game assets via Pixellab. Skips for asking ABOUT the pipeline, debugging, or non-art work.
---

# Art Pipeline (CLI Orchestrators)

This project has 4 CLI orchestrators that wrap Pixellab's v2 API into stage-by-stage art-generation pipelines. They support pause/review/resume so the human can check intermediate output before continuing, and a batch mode for unattended runs.

**You invoke them via the `Bash` tool.** Do NOT call the `mcp__muzharpg-pixellab__*` tools for these flows — those are for one-shot single-asset generation only.

## When to use which orchestrator

| Need | Orchestrator | Pipeline |
|---|---|---|
| Iso 地形 autotile (Wang 16-tile + iso 投影) | `autotile.py` | `generate_atlas` → `iso_project` → `verify_in_godot` |
| 大建築 (top-down ~30°) | `prop.py --kind=building` | `generate_object` → `chroma_key` |
| 小型 iso prop (燈籠、攤車裝飾) | `prop.py --kind=iso_prop` | 同上,但走 native iso 端點 |
| 劇情靜態 NPC (4 向 idle,不會移動) | `npc_static.py --directions 4` | `generate_4dir_base` → `add_idle_animation` → `compile_spritesheet` |
| 可能會升級成移動 NPC 的角色 | `npc_static.py` (預設 `--directions 8`) | 同上但生 8 方向,日後加 walk 不用重生 |
| 移動 NPC / player (8 向 walk + 4 向 idle) | `npc_moving.py` | `generate_8dir_base` → `add_idle_animation` → `add_walk_animation` → `compile_spritesheet` |

## Common CLI flags (all orchestrators)

- `--name <key>` — manifest 鍵 (必填)
- `--review-mode {none,stage}` — 預設 `stage` (每階段停);`none` = 一路跑完
- `--resume-from <stage_name>` — 從某 stage 起跑,前面 stage 由 manifest 讀已完成路徑
- `--force-restart-stage <name>` — 強制重跑某已完成 stage (可多次)

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
  --review-mode stage
```
→ 跑完 `generate_8dir_base` 後停。給使用者看 `output/characters/chen_ayi/rotations/*.png`。確認 OK 後:
```powershell
uv run python art_source/pipeline/orchestrators/npc_moving.py `
  --name chen_ayi --resume-from add_idle_animation
```

**確認絕對不會移動的劇情背景 NPC (省 credit):**
```powershell
uv run python art_source/pipeline/orchestrators/npc_static.py `
  --name street_vendor_01 `
  --description "elderly fruit seller, straw hat" `
  --directions 4 --review-mode none
```

**Iso autotile:**
```powershell
uv run python art_source/pipeline/orchestrators/autotile.py `
  --name market_grass_asphalt `
  --lower "green grass texture" --upper "dark asphalt road" `
  --transition-size 0.25 --transition-description "grey concrete curb"
```

**大建築 (high_top_down,不投影):**
```powershell
uv run python art_source/pipeline/orchestrators/prop.py `
  --name muzha_shophouse --kind building `
  --description "traditional taiwanese two-story shophouse, red brick" `
  --width 128 --height 128
```

**小型 iso 單格 prop:**
```powershell
uv run python art_source/pipeline/orchestrators/prop.py `
  --name red_lantern --kind iso_prop `
  --description "red paper lantern with gold tassel" --size 32
```

## Important constraints (don't violate)

- **`directions=4` 與 `directions=8` 是不同 character_id**,Pixellab 後端不通用。一旦選 4,日後想加 walk 動畫須**重新生成整隻角色**。預設 8 是安全選擇;只在使用者明確說「絕對不會動」才用 4。
- **`create_building` 不做 PIL iso 投影**。建築立體感不能被 affine 壓扁;接受 `high_top_down` ~30° 視角。
- **生成是 async 且不可預測**。標稱 ETA 180s 但實測可能 10-30 分鐘。`--review-mode stage` 跑完一個 stage 就 `sys.exit(0)`,不會 hang。
- **第一次跑必須給 `--description`** (`autotile` 是 `--lower`/`--upper`)。Resume 時可省略 — 從 manifest 讀。
- **不要直接呼叫底層 `pixellab_client` 函式**或 mcp_server 工具來重複實作 pipeline 邏輯。orchestrator 已封裝好;只需 Bash 調用。

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
