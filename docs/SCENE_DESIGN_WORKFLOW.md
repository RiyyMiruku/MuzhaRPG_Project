# 場景設計協作流程

給多人協作的場景設計人。**你只要負責場景視覺與設計，技術部分讓 AI 跑腳本。**

---

## 0. 你需要會的

- 把素材檔案放到指定資料夾
- 跟 AI 說一句話請它幫你跑腳本
- 在 Godot 編輯器拖節點、塗 TileMap、按存檔
- 基本 git pull / commit（或請程式組代為）

**不需要寫程式、不需要記指令、不需要懂 .tscn / .tres 格式。**

---

## 1. 三種你會做的事

### A. 我加了一批新的物件素材（Prop）

**例：** 你用 Pixellab 出了 16 張燈籠變體，丟到 `temp/` 下面。

**步驟：**

1. 把素材丟到 `temp/` 任意子資料夾（一個物件一個資料夾，內含 `tile1.png` ~ `tileN.png`）
2. 跟 AI 說：

   > 「我在 temp/ 加了新素材，幫我跑 import_assets.py」

3. AI 會：
   - 看每個資料夾的代表圖片
   - 判斷是 urban（人造）還是 nature（自然）
   - 判斷該不該擋角色（has_collision）跟碰撞範圍
   - 把 PNG 重命名移到 `game/assets/textures/environment/props/<category>/`
   - 為每張 PNG 生成對應的 `.tscn` prop 場景到 `game/src/maps/props/<category>/`
   - 回報處理了哪些東西

4. 在 Godot 按 `Ctrl+Shift+R` 重掃檔案
5. 拖 prop `.tscn` 到 zone 場景的 `YSortRoot` 底下

---

### B. 我加了新的 autotile（地形）素材

**例：** 你用 Pixellab Tilesets 模式出了 64×64 的 `autotile_grass_asphalt.png`，丟到 `game/assets/textures/environment/tilesets/<zone>/`。

**步驟：**

1. PNG 直接放到 `game/assets/textures/environment/tilesets/<zone>/autotile_*.png`
   - 命名規則：`autotile_<下層>_<上層>.png`，例 `autotile_grass_asphalt.png`
2. 跟 AI 說：

   > 「我加了新的 autotile，幫我跑 scaffold_zone.py」

3. AI 會：
   - 為該 zone 建 `<zone>_terrain.tres` TileSet（含 16 個 tile 完整 Pixellab 模板 + Terrain Sets + peering bits + 預設顏色）
   - 在 `zone_<zone>.tscn` 加上 `TileMapLayer_Ground` 節點並掛 TileSet
   - 不會動原本的 `Ground` ColorRect 佔位（你之後在編輯器裡刪）

4. 在 Godot 按 `Ctrl+Shift+R` 重掃
5. 開該 zone → 點 `TileMapLayer_Ground` → 下方 TileMap 面板 → **「地形」**分頁 → 直接刷
6. 刷完滿意後刪掉 `Ground` ColorRect 佔位 → `Ctrl+S`

> **不需要進 TileSet 編輯器手動設 peering bits**，scaffold_zone.py 已經寫好。
> 如果刷出來顏色反向（選 grass 出 asphalt），開該 .tres 把 `terrain_set_X/terrain_0/name` 跟 `terrain_1/name` 對調名稱跟顏色即可，peering bits 不用動。

---

### C. 我要在 zone 裡擺場景（最常做的事）

**步驟：**

1. Godot 左下檔案系統 → 雙擊 `game/src/maps/zones/zone_<name>.tscn`
2. **塗地形**（如果 TileMapLayer_Ground 已 attach TileSet 且 Terrain 已設好）：
   - 場景樹點 `TileMapLayer_Ground`
   - 下方 TileMap 面板 → Terrains 分頁 → 刷
3. **擺 prop**：
   - 左下檔案系統找 `src/maps/props/<category>/<name>.tscn`（**注意：拖 .tscn 檔，不要拖 PNG**）
   - 拖到 2D 視窗
   - 確認新節點在 `YSortRoot` 底下（不在的話用拖的丟進去）
4. `Ctrl+S` 存檔
5. `F6` 試玩這個 zone

### ⚠️ 最常見的陷阱：拖到 PNG 變 Sprite2D

**錯誤**：直接從檔案系統拖 `bamboo_04.png` 到場景。
- 結果是純 `Sprite2D` 節點，**沒有物理碰撞**，Player 直接穿過去。

**正確**：拖 `bamboo_04.tscn` 場景檔。
- 結果有 `StaticBody2D + CollisionShape2D + InteractArea`，會擋路也能互動。

怎麼分辨：場景樹節點是否有 ▶️ 展開箭頭（能展開看到 `Sprite2D / StaticBody2D / InteractArea` 子節點）。沒有的話就是 Sprite2D，刪掉重拖 .tscn。

### 避免做這些（破壞性）

- 不要動 `src/` 底下任何 `.gd` 程式檔
- 不要刪 `YSortRoot` / `Player` / `Transitions` 節點
- 不要改 prop 的 `Sprite2D.offset`（已自動設）
- 不要刪 `PropTemplate.tscn`
- 不要把 PNG 直接拖進場景（變 Sprite2D 沒碰撞，見上方）

如果不小心動到，按 `Ctrl+Z` 復原；存檔過了用 `git checkout <檔案>` 還原。

### 修改 prop 的碰撞範圍

例：擺了一棵高樹，希望 collision 只擋樹幹底部不擋樹冠：

1. 場景樹點開 prop → `StaticBody2D` → `CollisionShape2D`
2. Inspector 的 `Shape` → 改 size（如 `Vector2(16, 16)`）
3. `CollisionShape2D.position` 移到圖片底部（通常 `y = -8`）
4. **改 .tscn 主檔（`src/maps/props/<cat>/<name>.tscn`）→ 所有用到此 prop 的場景同步改變**
5. **只想改這一個個體 → 在 zone 場景內改即可，不影響其他**

詳細規範見 [game/src/maps/props/README.md](../game/src/maps/props/README.md) 跟 [② 場景製作流程 Step 7](../game/assets/textures/environment/2-scene-design.md)。

---

## 2. 給 AI 的「請幫我跑 X」一句話清單

複製貼上即可，不需自己想：

| 你想做的事 | 跟 AI 說 |
|---|---|
| 大批 prop 素材匯入 | `我在 temp/ 加了新素材，幫我跑 import_assets.py` |
| 新 autotile 設定 | `我加了新的 autotile，幫我跑 scaffold_zone.py` |
| 兩件事一起 | `我在 temp/ 加了新素材也加了新 autotile，幫我先跑 import_assets 再跑 scaffold_zone` |
| Godot 顯示 UID 錯誤 | `Godot 跳很多 Unrecognized UID 錯誤，幫我修` |
| 場景跑不起來 | `F6 跑 zone 出錯，這是錯誤訊息：[貼錯誤]` |
| Player 穿過 prop / 地形 | `Player 穿過 [prop名/地形]，幫我檢查物理層` |
| 地形邊界跳磚 / 錯位 | `[zone] 的地形拼接亂掉，幫我重生 .tres`（會跑 `scaffold_zone.py <zone> --force`） |
| 想改某個 prop 的碰撞 | `幫我把 [prop名] 的 collision 改成只擋底部 16x16` |
| 不知道怎麼開始 | `我想加一個新 zone 叫 X，要怎麼做？` |

---

## 3. 可用的腳本（給好奇的人看，平時不用記）

所有腳本在 `scripts/`，AI 會代為執行：

| 腳本 | 用途 | 詳細說明 |
|---|---|---|
| `import_assets.py` | TOML manifest → 重命名/搬 PNG + 生成 prop .tscn | [scripts/IMPORT_ASSETS_README.md](../scripts/IMPORT_ASSETS_README.md) |
| `scaffold_zone.py` | 為 zone 建 TileSet .tres + 加 TileMapLayer 節點 | 見腳本內 docstring |
| `generate_spritesheet.py` | NPC 序列圖 → 預編譯 spritesheet | 角色相關，不在場景設計範圍 |

執行範例（給 AI 看的）：

```bash
python scripts/import_assets.py --init temp/        # 1. 掃 temp/ 產生 manifest 草稿
python scripts/import_assets.py temp/import.toml    # 2. 正式匯入
python scripts/scaffold_zone.py                     # 為所有有 autotile 的 zone 建設定
python scripts/scaffold_zone.py nccu                # 只處理某 zone
```

---

## 4. 提交

做完一段場景工作後：

```bash
git pull                                              # 先拉最新
git add game/src/maps/ game/assets/textures/         # 只加場景跟素材
git commit -m "編輯 nccu 場景：地形 + 政大正門 prop 擺位"
git push
```

不熟 git 就請程式組代為提交（把改動列表給對方）。

---

## 5. 提交前最終自檢

push 前過一次：

- [ ] Godot 跑該 zone 沒有錯誤訊息（控制台無紅字）
- [ ] 角色走到 prop 後方時，prop 正確擋住角色（Y-sort）
- [ ] 角色撞不過樹幹/桿底，但能繞到後面
- [ ] 走在 asphalt / stone / 牆 / 物件 → 該擋的都擋（試走幾個邊界）
- [ ] Terrain 邊緣融合自然，沒有破圖
- [ ] 場景樹的 prop 都是有 ▶️ 展開箭頭的實例（不是純 Sprite2D）
- [ ] `git status` 只動到 `game/src/maps/` 跟 `game/assets/textures/`，沒誤動其他

---

## 6. 物理碰撞層號（除錯用）

| Layer | 用途 |
|---|---|
| 1 | Player 自己 + Terrain（autotile）|
| 2 | NPC |
| 4 | Prop StaticBody2D |

Player.collision_mask = `7`（=1+2+4，會擋 terrain + NPC + prop）

如果 Player 穿過某個東西 → 那東西的 `collision_layer` 不在 1/2/4 之內，或物件根本沒 StaticBody2D。

---

## 相關文件

- [① 素材製作與歸檔](../game/assets/textures/environment/1-asset-creation.md) — Pixellab 設定 / 命名規範 / 像素規格
- [② 場景製作流程](../game/assets/textures/environment/2-scene-design.md) — 詳細 Godot 操作
- [③ AI Prompt 範本（手動複雜版）](../game/assets/textures/environment/3-ai-prompt.md) — 大段 prompt（一般不需要，本文件的一句話清單就夠）
- [scripts/IMPORT_ASSETS_README.md](../scripts/IMPORT_ASSETS_README.md) — 匯入腳本詳細說明
