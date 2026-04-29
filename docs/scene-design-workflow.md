# 場景設計協作流程（速查）

> **對象**：場景設計人。**用途**：一頁速查 + 跟 AI 對話的指令清單。
> **詳細教學**：[2-scene-design.md](../game/assets/textures/environment/2-scene-design.md)

---

## 0. 必要技能

- 把素材檔丟到指定資料夾
- 跟 AI 講一句話請它跑腳本
- Godot 編輯器拖節點、塗 TileMap、`Ctrl+S` 存檔
- 基本 git pull / commit（不熟可請程式組代理）

---

## 1. 三種你會做的事

### A. 加新 prop 素材

1. 素材丟 `temp/<物件名>/tile1.png ~ tileN.png`
2. 跟 AI 說：`我在 temp/ 加了新素材，幫我跑 import_assets.py`
3. Godot `Ctrl+Shift+R` 重掃
4. 從檔案系統拖 `src/maps/props/<cat>/<name>.tscn` 到 zone 的 `YSortRoot`

### B. 加新 autotile（地形）

1. PNG 命名 `autotile_<下層>_<上層>.png` 丟 `game/assets/textures/environment/tilesets/<zone>/`
2. Godot `Ctrl+Shift+R`
3. 跟 AI 說：`我加了 [zone] 的新 autotile PNG，幫我加進 TileMapDual`
4. 點 zone 的 `TileMapDual` 節點 → TileMap 面板「地形」分頁 → 選 `FG -<png名>` 矩形刷

> 詳細 TileMapDual 設定見 [tilemapdual-guide.md](tilemapdual-guide.md)。

### C. 在 zone 擺場景（最常做）

1. 雙擊 `game/src/maps/zones/zone_<name>.tscn`
2. **塗地形**：點 `TileMapDual` → 地形分頁 → 矩形刷
3. **擺 prop**：拖 `.tscn` 到 `YSortRoot` 底下（**不是拖 PNG**，見下方陷阱）
4. `Ctrl+S` → `F6` 試玩

---

## ⚠️ 三個最常見陷阱

| 症狀 | 原因 | 修法 |
|---|---|---|
| Player 穿過 prop | 拖了 PNG（變 Sprite2D 沒碰撞）| 刪掉重拖 `.tscn` 場景檔 |
| Player 穿過地形 | Player.collision_mask 沒含對應 layer | 改成 `7`（=1+2+4，全擋） |
| 地形邊界破圖 | TileMapDual preset 對應錯 | 跟 AI 說 `[zone] TileMapDual 拼接怪，檢查 preset 對應` |

**辨識「拖對東西」**：場景樹節點要有 ▶️ 展開箭頭，能看到 `Sprite2D + StaticBody2D + InteractArea`。沒有的話就是純 Sprite2D。

---

## 2. 跟 AI 講的一句話清單

複製貼上即可：

| 想做的事 | 講這句 |
|---|---|
| 大批 prop 素材匯入 | `我在 temp/ 加了新素材，幫我跑 import_assets.py` |
| 加新 autotile PNG | `我加了 [zone] 的新 autotile PNG，幫我加進 TileMapDual` |
| Player 穿過某物 | `Player 穿過 [prop名/地形]，幫我檢查物理層` |
| 地形邊界錯位 | `[zone] 的 TileMapDual 拼接怪，幫我檢查 preset 對應` |
| 改 prop 碰撞範圍 | `幫我把 [prop名] 的 collision 改成只擋底部 16x16` |
| Godot UID 錯誤 | `Godot 跳很多 Unrecognized UID 錯誤，幫我修` |
| F6 跑場景出錯 | `F6 跑 [zone] 出錯，這是錯誤訊息：[貼錯誤]` |
| 不知道怎麼開始 | `我想加一個新 zone 叫 X，要怎麼做？` |

---

## 3. 提交流程

```bash
git pull
git add game/src/maps/ game/assets/textures/
git commit -m "編輯 [zone] 場景：地形 + prop 擺位"
git push
```

### 提交前自檢

- [ ] Godot 控制台無紅字
- [ ] 角色繞到 prop 後方時 prop 蓋住腳底以上（Y-sort 正常）
- [ ] 該擋的都擋（樹幹、牆、asphalt / stone 區）
- [ ] 場景樹的 prop 都有 ▶️ 展開箭頭（非純 Sprite2D）
- [ ] `git status` 只動到 `game/src/maps/` 跟 `game/assets/textures/`

---

## 4. 不要動的東西

- `src/` 底下任何 `.gd` 程式檔
- `YSortRoot` / `Player` / `Transitions` 節點
- `PropTemplate.tscn`
- prop 的 `Sprite2D.offset`（已自動處理）

不小心動到：`Ctrl+Z` 或 `git checkout <檔案>`。

---

## 相關文件

| 文件 | 用途 |
|---|---|
| [docs/INDEX.md](INDEX.md) | 全部文檔導覽 |
| [2-scene-design.md](../game/assets/textures/environment/2-scene-design.md) | 詳細 Godot 操作（含修改 collision、debug） |
| [1-asset-creation.md](../game/assets/textures/environment/1-asset-creation.md) | Pixellab 設定、命名規範 |
| [tilemapdual-guide.md](tilemapdual-guide.md) | 地形系統完整用法 |
| [props/README.md](../game/src/maps/props/README.md) | Prop 程式契約、collision 規範 |
| [scripts/import-assets-guide.md](../scripts/import-assets-guide.md) | import_assets.py 細節 |
