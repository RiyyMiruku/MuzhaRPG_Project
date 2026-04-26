# 大量素材自動匯入

把一批 Pixellab / Aseprite 出的 PNG 從 `temp/` 自動搬進專案結構並產生 Godot prop 場景。

設計成「美術 + AI」協作：美術只說「我有什麼東西要進專案」，AI 寫 manifest 跑腳本。

> 這是 prop 匯入的詳細說明。如果你是場景設計人，看 [docs/SCENE_DESIGN_WORKFLOW.md](../docs/SCENE_DESIGN_WORKFLOW.md) 即可（內含跟 AI 講的一句話清單）。
>
> autotile（地形）相關的腳本是 `scripts/scaffold_zone.py`，用法見該腳本內 docstring 或 SCENE_DESIGN_WORKFLOW.md。

---

## 美術的工作

1. 把素材丟到 `temp/` 任意子資料夾下（每個物件一個資料夾，內含 `tile1.png` ~ `tileN.png`）
2. 跟 AI 說：「我在 temp/ 加了新素材，幫我跑 import_assets.py」
3. 等 AI 回報，然後開 Godot `Ctrl+Shift+R` 重新掃描檔案
4. 拖 `.tscn` 到場景

---

## AI 的工作（4 步）

### 1. 掃描 + 建 manifest

```bash
python scripts/import_assets.py --init temp/
```

會產生 `temp/import.toml`，每個 PNG 資料夾一個 `[[items]]` 區塊，預填猜測值。

### 2. 修正 manifest（**這步是判斷重點**）

打開 `temp/import.toml`，依視覺檢查每張代表圖片，調整：

- `type` — `prop`（單獨擺）或 `autotile`（地形塗刷，需 Pixellab 4-grid 格式）
- `category` — `urban`（人造）或 `nature`（自然）
- `zone` — autotile 才需要（`market` / `nccu` / `riverside` / `zhinan`）
- `has_collision` — 角色該不該被擋住？
- `collision` — 碰撞範圍預設：
  - `none` — 無碰撞（地板、空中懸掛物）
  - `bottom_16x8` — 底部一條（草叢、小花圃）
  - `bottom_16x16` — 底部一格（樹幹、桿底）
  - `full` — 整張矩形（攤位、桌子）
  - `"WxH"` — 自訂尺寸（例：`"24x12"`）

### 3. 跑匯入

先 dry-run 確認：

```bash
python scripts/import_assets.py --dry-run temp/import.toml
```

確認沒問題再正式跑：

```bash
python scripts/import_assets.py temp/import.toml
```

### 4. 回報美術

- 列出處理了哪些資料夾、進到哪個目錄、生成幾個 .tscn
- 提醒去 Godot 按 `Ctrl+Shift+R` 重掃

---

## 安全機制

- **未列出的資料夾會 WARNING**：`temp/` 內有 PNG 但 manifest 沒列的會印出來，不會被靜默忽略
- **`--dry-run`**：先看會做什麼再決定要不要跑
- **TSCN UID 由檔名 SHA1 生成**：同名重跑會產生同 UID（不會在 Godot 裡產生孤兒引用）
- **沿用 `PropTemplate.tscn`**：所有生成的 prop 都繼承共同範本，之後改 template 全部跟著改

---

## 不該用這個腳本的時候

- **單一張素材**：直接手動丟進 `props/<category>/` 比較快
- **Autotile 需要 bitmask 設定**：腳本只搬 PNG，不會建 `.tres` TileSet（那部分需要在 Godot 編輯器或請 AI 依 [3-ai-prompt.md](../game/assets/textures/environment/3-ai-prompt.md) B 段處理）
- **形狀很特殊的 prop**（樹冠 + 樹幹要分層）：跑完後再開 .tscn 微調 collision

---

## 範例 manifest

```toml
# 紅燈籠（懸掛，不該擋人）
[[items]]
folder = "temp/tilesets/market/red_lantern"
type = "prop"
category = "urban"
has_collision = false
collision = "none"

# 攤位（整個擋住）
[[items]]
folder = "temp/tilesets/market/vendor_stall_frame"
type = "prop"
category = "urban"
has_collision = true
collision = "full"

# 樹（只擋樹幹）
[[items]]
folder = "temp/tilesets/nccu/campus_tree"
type = "prop"
category = "nature"
has_collision = true
collision = "bottom_16x16"

# 地形（autotile 4-grid）
[[items]]
folder = "temp/tilesets/nccu/grass_asphalt"
type = "autotile"
zone = "nccu"
```
