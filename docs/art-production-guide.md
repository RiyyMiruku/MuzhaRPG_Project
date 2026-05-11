# 美術生產手冊

> **給誰看:** 美術組成員 + 偶爾跑 pipeline 的開發者
> **這份不講:** 內部架構(看 [pipeline/README.md](../pipeline/README.md))、做美術風格指南(看 [1-asset-creation.md](../game/assets/textures/environment/1-asset-creation.md))

每個資產(角色、autotile、prop)都從 **Pixellab API** 生圖、後處理、自動匯入 Godot。**整條流程一個指令跑完**,你不需要手動搬檔。

---

## 兩種使用方式 — 看心情選

| 場景 | 用哪個 |
|---|---|
| 我已經想好 prompt,要做一個資產 | **CLI orchestrator** — 一條指令搞定 |
| 我想看現在已經做了什麼、修改 prompt、重做某階段 | **Web UI** (asset dashboard) |
| 我要做整批新章節的資產 | 兩個搭配 — CLI 批次跑,UI 監控進度 |

---

## A. CLI Orchestrator(快速生成)

每個資產類型對應一個 orchestrator 腳本。在專案根目錄執行:

### A1. 移動 NPC / 玩家(8 方向 + walk 動畫)

```powershell
uv run python pipeline/orchestrators/npc_moving.py `
  --name chen_ayi `
  --description "middle-aged taiwanese market vendor woman, red floral shirt, beige apron, friendly smile" `
  --zone market --category vendor `
  --review-mode none
```

- 跑 5 階段: 8 方向 base → idle 動畫(4 向)→ walk 動畫(8 向)→ 編譯 spritesheet → 匯入 Godot
- 完整跑完約 5-15 分鐘
- 產出 → `game/assets/textures/characters/chen_ayi.{png,json}`,直接可用

### A2. 劇情背景 NPC(只有 idle,不會走路)

```powershell
uv run python pipeline/orchestrators/npc_static.py `
  --name shopkeeper_li `
  --description "elderly taiwanese male shopkeeper, blue shirt, glasses" `
  --zone market --category vendor `
  --directions 4 --review-mode none
```

- `--directions 4`(預設 8)走 4 方向,省一半 credit
- ⚠️ **角色一旦選 4-dir,日後想加 walk 必須整隻重生**(Pixellab character_id 跟方向綁定)

### A3. Prop / 建築

```powershell
# 小型 iso prop(燈籠、攤車裝飾)
uv run python pipeline/orchestrators/prop.py `
  --name lantern_red --kind iso_prop `
  --description "red paper lantern with gold tassel" `
  --zone market --category decoration --size 32

# 大型建築(廟、街屋)
uv run python pipeline/orchestrators/prop.py `
  --name muzha_shophouse --kind building `
  --description "traditional taiwanese two-story red brick shophouse" `
  --zone market --category building --width 128 --height 128
```

碰撞旗標(只對 prop):
- `--collision bottom_16x16` (預設,適合樹幹、桿底)
- `--collision full` (整張矩形,適合攤位、桌子)
- `--collision none` (空中懸掛物、地板)
- `--no-collision` (完全不生 StaticBody)

### A4. Autotile 地形

```powershell
uv run python pipeline/orchestrators/autotile.py `
  --name market_grass_asphalt `
  --lower "green grass texture" `
  --upper "dark asphalt road" `
  --zone market --category terrain `
  --transition-size 0.25 --transition-description "grey concrete curb"
```

產出 iso 投影成品 → `game/assets/textures/tilesets/<name>.png`,在 Godot 裡用 TileMapDual addon 拉地形。

---

## B. Web UI(Asset Dashboard)

視覺化看現有資產 + 編輯 prompt + 重生某階段。

### 啟動

```powershell
# 第一次(裝前端依賴 + 編譯)
cd tools/asset_dashboard/frontend
pnpm install
pnpm build
cd ../../..

# 之後每次啟動
uv run uvicorn tools.asset_dashboard.backend.server:app --port 8765
```

開瀏覽器 → http://localhost:8765/

### 介面

**頂部:** 搜尋 + 篩選(章節 / 類型 / 完成狀態)
**主區:** 資產卡片網格,每張卡:
- 縮圖(找代表圖,通常是 south 方向或 iso 成品)
- 名稱 + 進度(`3/5` 代表 5 階段完成 3 個)
- Tags(zone、category、chapter)
- 每階段勾選狀態(✓ / ○)
- "Show prompts ▾" 按鈕展開 prompt 編輯區

**右下角:** 浮動 Jobs 按鈕,看正在跑的 orchestrator 子行程 + log。

### Prompt 編輯流程

每階段有 prompt 文字框,兩種狀態:

| 狀態 | 視覺 | 行為 |
|---|---|---|
| **未實現(尚未生成)** | 黃色 unlock 圖示 + 可編輯 textarea | 改完按 **Submit** → 直接寫進 manifest,下次跑該階段會用新 prompt |
| **已實現(圖已產出)** | 灰色 lock 圖示 + 唯讀 textarea + **Remake** 按鈕 | 按 Remake → 確認框 → 解鎖編輯 → 改完按 **Remake & Submit** → 觸發 orchestrator 重生該階段 |

⚠️ **Remake 是精準模式,不會 cascade**:重生 stage 2 (idle 動畫) 後,stage 3 (walk) 跟 stage 4-5 不會自動失效。如果你想連 walk 一起重生,得分別點各自的 Remake。

### Dev mode(前端 hot reload,改 .tsx 即時看到)

```powershell
# 終端機 1:後端
uv run uvicorn tools.asset_dashboard.backend.server:app --reload --port 8765

# 終端機 2:前端
cd tools/asset_dashboard/frontend
pnpm dev
```

開 http://localhost:5173/(Vite 會 proxy /api 到 8765)。

---

## C. 中斷續跑 / 手動干預

orchestrator 預設 `--review-mode stage`,每階段完跑會停下讓你檢視。檢視 OK 後用 `--resume-from <next-stage>` 繼續。範例:

```powershell
# 跑完 stage 1 自動停
uv run python pipeline/orchestrators/npc_moving.py `
  --name chen_ayi --description "..." --review-mode stage
# → 看 art_source/characters/chen_ayi/rotations/*.png

# 看了喜歡 → 繼續
uv run python pipeline/orchestrators/npc_moving.py `
  --name chen_ayi --resume-from add_idle_animation --review-mode stage

# 看了不喜歡 → 換 prompt 重跑 stage 1
uv run python pipeline/orchestrators/npc_moving.py `
  --name chen_ayi --description "<新 prompt>" `
  --force-restart-stage generate_8dir_base --review-mode stage
```

或更方便:用 dashboard 點 Remake。

---

## D. 命名規範

資產名是 manifest 鍵,**腳本會強制檢查**:

```
^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$    長度 3–64
```

建議命名結構:
- **指名 NPC**: `chen_ayi`, `lin_zhiwei`
- **泛用 NPC**: `vendor_market_01`, `student_nccu_03`
- **Autotile**: `market_grass_asphalt`, `riverside_water_sand`
- **建築**: `nccu_dormitory`, `market_shophouse_01`
- **Iso prop**: `lantern_red`, `cart_fruit`

**不要**把 zone/category/chapter 寫進名字 — 用 `--zone` / `--category` flag 寫入 tags。Tags 可以後續改、可以多重歸屬,name 一旦定了改名會破 Godot UID 引用。

---

## E. 常見問題

### Q: 跑很久(>10 分鐘)還沒完
A: Pixellab API 名目 ETA 180 秒,實測常 10-30 分鐘,正常。看 Web UI 的 Jobs 浮動視窗確認 process 還活著。

### Q: 想看 prompt 改完之後實際長什麼樣再決定要不要重生
A: 不行,Pixellab 不支援 dry-run。Prompt 改了就只能跑下去看結果。建議先用便宜的 4-dir static NPC 試 prompt 風格,確認 OK 再升級 8-dir moving。

### Q: 我改了 .tsx,Web UI 沒變
A: 跑 `pnpm dev` 才有 hot reload。如果你跑的是 `uvicorn` + `pnpm build` 的 production 模式,改 .tsx 後要重跑 `pnpm build`。

### Q: orchestrator 跑到一半失敗,manifest 留下髒資料
A: 不會。manifest 用 `stages` 紀錄已完成,失敗的階段不會被標記。重跑會從上次失敗的階段繼續。如果想完全重做,刪掉 manifest 該資產整個 entry。

### Q: 我要把資產從一章節改到另一章節
A: 改 manifest 的 `tags`,把 `chapter:1` 改成 `chapter:2`。或在 dashboard 上 — 目前 UI 還不支援 tag 編輯,直接改 `art_source/manifest.json` 也行(它是 single source of truth)。

---

## 相關文檔

- [pipeline/README.md](../pipeline/README.md) — 內部架構、orchestrator 細節、底層 API
- [tools/asset_dashboard/README.md](../tools/asset_dashboard/README.md) — Web UI 詳細端點 + 限制
- [docs/asset-naming-convention.md](asset-naming-convention.md) — 命名規範細節
- [docs/scene-design-workflow.md](scene-design-workflow.md) — 拿到資產後怎麼放進場景
