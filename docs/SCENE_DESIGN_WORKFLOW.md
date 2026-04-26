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
   - 為該 zone 建 `<zone>_terrain.tres` TileSet（已掛好 atlas + 切好 4 格）
   - 在 `zone_<zone>.tscn` 加上 `TileMapLayer_Ground` 節點，並 attach TileSet
   - 不會動原本的 `Ground` ColorRect 佔位（你之後在編輯器裡刪）

4. 在 Godot 開該 zone scene
5. 點選 `TileMapLayer_Ground` → Inspector 的 TileSet → 點開
6. **TileSet 編輯器** → `Terrain Sets` 分頁 → 新增 Terrain Set（mode = Match Corners and Sides）→ 加 2 個 Terrain（如 `grass`、`asphalt`）
7. `Tiles` 分頁 → 用 Paint 模式對 4 個 tile 設 peering bits（哪邊算 grass、哪邊算 asphalt）
8. 切到 `TileMap 面板` 的 **Terrains** 分頁 → 選 terrain → 在 2D 視窗刷地板
9. 刷完滿意後刪掉場景樹的 `Ground` ColorRect 佔位
10. `Ctrl+S` 存檔

> Terrain Set 設定只要做一次，之後同一 zone 的不同地圖都會用同一個 TileSet。

---

### C. 我要在 zone 裡擺場景（最常做的事）

**步驟：**

1. Godot 左下檔案系統 → 雙擊 `game/src/maps/zones/zone_<name>.tscn`
2. **塗地形**（如果 TileMapLayer_Ground 已 attach TileSet 且 Terrain 已設好）：
   - 場景樹點 `TileMapLayer_Ground`
   - 下方 TileMap 面板 → Terrains 分頁 → 刷
3. **擺 prop**：
   - 左下檔案系統找 `src/maps/props/<category>/<name>.tscn`
   - 拖到 2D 視窗
   - 確認新節點在 `YSortRoot` 底下（不在的話用拖的丟進去）
4. `Ctrl+S` 存檔
5. `F6` 試玩這個 zone

**避免做這些**（破壞性）：

- 不要動 `src/` 底下任何 `.gd` 程式檔
- 不要刪 `YSortRoot` / `Player` / `Transitions` 節點
- 不要改 prop 的 `Sprite2D.offset`（已自動設）
- 不要刪 `PropTemplate.tscn`

如果不小心動到，按 `Ctrl+Z` 復原；存檔過了用 `git checkout <檔案>` 還原。

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
- [ ] Terrain 邊緣融合自然，沒有破圖
- [ ] `git status` 只動到 `game/src/maps/` 跟 `game/assets/textures/`，沒誤動其他

---

## 相關文件

- [① 素材製作與歸檔](../game/assets/textures/environment/1-asset-creation.md) — Pixellab 設定 / 命名規範 / 像素規格
- [② 場景製作流程](../game/assets/textures/environment/2-scene-design.md) — 詳細 Godot 操作
- [③ AI Prompt 範本（手動複雜版）](../game/assets/textures/environment/3-ai-prompt.md) — 大段 prompt（一般不需要，本文件的一句話清單就夠）
- [scripts/IMPORT_ASSETS_README.md](../scripts/IMPORT_ASSETS_README.md) — 匯入腳本詳細說明
