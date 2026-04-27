# ② 場景製作流程（給地圖設計人）

本文涵蓋**拿到素材後如何在 Godot 中組成場景**。前置作業（素材製作與歸檔）見 [① 素材製作與歸檔](1-asset-creation.md)。

> **多人協作入口**：[docs/SCENE_DESIGN_WORKFLOW.md](../../../../docs/SCENE_DESIGN_WORKFLOW.md) 是給場景設計人的精簡入口，本文是詳細的 Godot 操作說明。

---

## 0. 你需要會的

- 開啟 Godot 編輯器、雙擊檔案、滑鼠拖拉
- 基本 git commit / push（也可以請程式組代為 push）

**不需要寫程式**，全程用 Godot 編輯器的視覺工具。

---

## 1. 場景製作流程總覽

```
┌──────────────────────┐
│ 0. 確認素材已歸檔    │  ← ① 素材製作流程已完成
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 1. 給 AI 跑 prompt   │  ← AI 自動補 .tres / .tscn
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 2. 打開 Godot 編輯器 │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 3. 塗地形            │  ← Terrain 筆刷
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 4. 擺 prop           │  ← 拖 .tscn 到 YSortRoot
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 5. 存檔 + F6 測試    │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ 6. commit / push     │
└──────────────────────┘
```

---

## Step 1：給 AI 跑 prompt 補 Godot 結構

打開專案根目錄的 Claude Code（或其他能讀寫專案檔案的 AI 助手）：

| 你做的事 | 跟 AI 說 |
|---|---|
| 把新 prop PNG 丟進 `temp/` | `我在 temp/ 加了新素材，幫我跑 import_assets.py` |
| 把新 autotile PNG 丟進 `tilesets/<zone>/` | `我加了新 autotile，幫我跑 scaffold_zone.py` |
| 兩件事一起 | `我在 temp/ 加素材也加 autotile，先跑 import_assets 再跑 scaffold_zone` |

AI 會自動：

- **import_assets.py**：判斷分類 → 重命名 PNG → 生 prop `.tscn`（含 StaticBody2D + InteractArea）
- **scaffold_zone.py**：建 `<zone>_terrain.tres`（含 16 個 tile 的完整 Pixellab 模板與 peering bits）→ 在 `zone_<zone>.tscn` 加 `TileMapLayer_Ground` 並掛 TileSet

完成後在 Godot 左下角檔案系統看到新檔案（按 `Ctrl+Shift+R` 重掃）。

---

## Step 2：打開 Godot 編輯器

1. 啟動 Godot 4.6
2. 第一次：「匯入」→ 選 `game/project.godot`
3. 左下角檔案系統 → 雙擊 `src/maps/zones/zone_<name>.tscn`（要編輯哪個 zone 開哪個）
4. 中央視窗顯示 2D 場景

---

## Step 3：塗 autotile 地形

### 一般情況（scaffold_zone.py 跑過後）

`scaffold_zone.py` 已經自動寫好 16 個 tile 的 peering bits 跟 Terrain Sets，**不需要進 TileSet 編輯器手動設定**。

1. 場景樹點 `TileMapLayer_Ground`
2. 視窗下方 TileMap 面板 → **「地形」**分頁
3. 左側 palette 看到該 zone 的 terrain（dirt/stone、grass/asphalt、water/concrete...）
4. **選一個 terrain → 上方工具列選筆刷形狀**（畫筆／線／矩形／油漆桶）
5. 在 2D 視窗左鍵拖動 → Godot 自動拼接邊界

### 工具列說明

| 工具 | 用途 |
|---|---|
| 畫筆 | 點/拖一格一格刷 |
| 線 | 兩點連線 |
| **矩形** | 拉框填滿（最常用） |
| 油漆桶 | 填滿封閉區域 |
| 吸取 | 從畫面取色 |
| 橡皮擦 | 移除 |

### 視覺反向時

刷出來顏色跟你預期的相反（例：選 grass 結果出現 asphalt）：
- 開該 zone 的 `.tres` 檔（例 `src/maps/tilesets/market_terrain.tres`）
- 找到 `terrain_set_X/terrain_0/name` 跟 `terrain_set_X/terrain_1/name`，**對調名稱跟顏色**
- peering bits 不用動

### Pixellab 素材必看

如果你要重新標 peering bits（自己畫的素材或 Pixellab 以外來源）：

- **Mode 必須選 `Match Corners` (mode 1)**，不是 Match Corners and Sides。Pixellab 的 4×4 = 16 tile 對應 4 bit corner = 16 種組合，剛好夠。Match Corners and Sides 需要 256 tile。
- 每塊 tile 標 4 個角 + 1 個中心點。每個角必須**只屬於一個 terrain**（不能漏標）。
- Pixellab 4×4 PNG 的位置 → bitmask 對應規則記錄在 `scripts/scaffold_zone.py` 的 `PIXELLAB_LAYOUT` dict。

---

## Step 4：擺 prop（重要：用 .tscn 不要用 PNG）

### 正確方式

1. 左下檔案系統找 `src/maps/props/<category>/<name>.tscn`（例：`bamboo_04.tscn`）
2. **拖 `.tscn` 檔**到 2D 視窗想要的位置
3. 確認新節點在場景樹的 `YSortRoot` 底下（不是的話拖進去）
4. 重複擺多個

### ⚠️ 陷阱：不要用 Sprite2D + PNG

**錯誤示範**：直接拖 `bamboo_04.png`（圖片檔）到場景。

```
❌ [node name="Bamboo04" type="Sprite2D" ...]   ← 純圖，無物理！
✅ [node name="Bamboo04" parent="YSortRoot" instance=ExtResource("..._tscn")]
```

**為什麼有差**：`.tscn` 場景包含 `StaticBody2D` + `CollisionShape2D` + `InteractArea`，**Player 走過去會被擋住**。純 Sprite2D 只是貼圖，**Player 直接穿越**。

### 怎麼分辨自己擺的是哪種？

看場景樹節點 icon：

| 顯示 | 是什麼 |
|---|---|
| 綠色 Sprite2D 圖示，無 ▶️ 展開箭頭 | ❌ 純 Sprite2D（沒物理） |
| 灰色「場景」icon，有 ▶️ 展開後可看到 `Sprite2D` + `StaticBody2D` + `InteractArea` | ✅ Prop 實例（有物理） |

擺錯了？選中節點按 `Delete`，從檔案系統重新拖 `.tscn` 進去。

> Y-sort 會自動處理遮擋順序 — 角色繞到樹後方會自動被擋；走到樹前方會擋住樹幹。**不需要調 z-index**。

---

## Step 5：存檔 + 測試

1. `Ctrl+S` 存檔
2. 按 `F6`（或右上角 ▶）「執行此場景」
3. 角色出現可走動，檢查：
   - **物理**：撞不過樹幹/桿底、走到 asphalt/stone 區也撞牆 → 沒擋住見 Step 6 troubleshoot
   - **Y-sort**：角色繞到 prop 後方時 prop 應蓋住角色腳底以上
   - **地形邊界**：自然融合，沒有破圖 / 跳磚

---

## Step 6：常見問題排查

### Player 穿過 prop / 地形

**檢查 1**：場景樹的節點是 `instance=` 還是 `type="Sprite2D"`？
- 如果是 Sprite2D → 換成 prop 實例（見 Step 4 ⚠️）

**檢查 2**：地形 `.tres` 的 `physics_layer_0/collision_layer` 是不是 `1`？Player 的 `collision_mask` 必須包含 layer 1（值是 7 = 1+2+4 涵蓋全部 obstacle layer）。

**檢查 3**：開 Player.tscn 確認：
```
collision_layer = 1
collision_mask = 7   ← 必須包含 1（terrain）+ 2（NPC）+ 4（prop）
```

### 地形邊界錯位 / 跳磚

代表 peering bits 標錯，最常見原因：
- Mode 設成 `0` (Match Corners and Sides) 而不是 `1` (Match Corners)
- 用了 2×2 而不是 4×4 layout

讓 AI 跑 `python scripts/scaffold_zone.py <zone> --force` 重生即可。

### Prop 擺位 Y-sort 錯亂

- 確認 prop 在 `YSortRoot` 底下
- 確認 PNG 腳底錨點正確（透過 import_assets.py 進來的會自動處理）

### Godot 顯示 Unrecognized UID

按 `Ctrl+Shift+R` 重掃，仍有錯就跟 AI 說「Godot 跳 UID 錯誤幫我修」。

---

## Step 7：修改 prop 的碰撞範圍

例：你擺了一棵高樹，但 collision 太大，希望只擋樹幹底部 16×16，不擋樹冠：

1. 場景樹點開該 prop（例 `Tree01`）→ 點開 `StaticBody2D` → 點 `CollisionShape2D`
2. Inspector 看 `Shape` 屬性：
   - 如果是 `RectangleShape2D` → 改 `Size = Vector2(16, 16)`
   - 改 `CollisionShape2D.position` 把碰撞區移到圖片底部（通常 y = -8）
3. `Ctrl+S`

**要套用到所有同類 prop？** 改該 prop 的 `.tscn` 主檔（`src/maps/props/<category>/<name>.tscn`），每個場景使用該 .tscn 都會跟著變。

**只想改這一個 prop 不影響其他？** 只在 zone 場景內改（不會影響別的 zone）。

### 高 prop 的 collision 規範（不要全圖擋路）

| PNG 高度 | 建議 collision |
|---|---|
| ≤ 16 px（花圃、小石頭） | `has_collision = false` 完全可走過 |
| 17–48 px（椅、燈、桶） | 整體矩形 |
| > 48 px（樹、電線桿、招牌） | **只擋底部 16×16**，角色可繞到後方 |

完整規範見 [game/src/maps/props/README.md](../../../src/maps/props/README.md)。

---

## Step 8：提交

```bash
git pull                                              # 先拉最新
git add game/src/maps/ game/assets/textures/         # 只加場景跟素材
git commit -m "編輯 nccu 場景：地形 + 政大正門 prop 擺位"
git push
```

不熟 git 就請程式組代為提交（把改動列表給對方）。

---

## Godot 操作速查（第一次用必看）

| 動作 | 操作 |
| --- | --- |
| 打開場景 | 雙擊 `.tscn` 檔 |
| 在場景中加新節點 | 場景樹按 `+` 或 `Ctrl+A` |
| 移動節點 | 點選後拖拉，或按 `W` 進入移動模式 |
| 刪除節點 | 選中按 `Delete` |
| 場景樹拖移層級 | 直接拖（注意：prop 必須在 `YSortRoot` 底下） |
| 縮放視窗 | 滑鼠滾輪 |
| 平移視窗 | 中鍵拖、或空白鍵+左鍵拖 |
| 存檔 | `Ctrl+S` |
| 執行此場景 | `F6` |
| 復原 | `Ctrl+Z` |
| 重新掃描檔案 | `Ctrl+Shift+R` |
| 重新載入儲存的場景 | 場景 → 重新載入儲存的場景 |

### ⚠️ 避免做這些

- 不要動 `src/` 底下任何 `.gd` 程式檔
- 不要刪除 `YSortRoot`、`Player`、`Transitions` 節點
- 不要改 prop 的 `Sprite2D.offset`（已自動設）
- 不要刪除既有的 `.tres` 或 `PropTemplate.tscn`
- 不要把 PNG 直接拖進場景（會變 Sprite2D 沒碰撞）— 一定要拖 `.tscn`

如果不小心動到，按 `Ctrl+Z` 復原；存檔過了就用 `git checkout <檔案>` 還原。

---

## 提交前最終自檢

push 前再過一次：

- [ ] Godot 中執行該 zone 沒有錯誤訊息（控制台無紅字）
- [ ] 角色走到 prop 後方時，prop 正確擋住角色（Y-sort）
- [ ] 角色撞不過樹幹/桿底，但能繞到後面
- [ ] 走在 asphalt / stone / 牆 / 物件 → 該擋的都擋
- [ ] 地形 Terrain 邊緣融合自然，沒有破圖
- [ ] `git diff` 只動到 `assets/textures/environment/` 與 `src/maps/`，沒誤動其他檔案

---

## 物理碰撞層號對照（除錯用）

| Layer | 用途 | 設在哪 |
|---|---|---|
| 1 | Player + Terrain（autotile）| Player.tscn / TileSet `physics_layer_0/collision_layer` |
| 2 | NPC | BaseNPC.tscn |
| 4 | Prop StaticBody2D | PropTemplate.tscn |

Player.collision_mask = `7`（=1+2+4，會擋 terrain + NPC + prop 全部）
