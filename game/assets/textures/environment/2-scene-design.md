# ② 場景製作流程（給地圖設計人）

本文涵蓋**拿到素材後如何在 Godot 中組成場景**。前置作業（素材製作與歸檔）見 [① 素材製作與歸檔](1-asset-creation.md)。

> 不限於美術組 — 任何人想參與場景擺位都可以照本文流程操作。

---

## 0. 你需要會的

- 開啟 Godot 編輯器、雙擊檔案
- 滑鼠拖拉
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
│ 1. 給 AI 跑 prompt   │  ← AI 自動補 Godot 結構（.tres / .tscn）
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

打開專案根目錄的 Claude Code（或其他能讀寫專案檔案的 AI 助手），把 [③ AI Prompt 範本](3-ai-prompt.md) 的整段內容貼給 AI 送出。

AI 會自動：

- 為新的 autotile PNG 建立 `<zone>_terrain.tres` TileSet 資源（含 Terrain Set 與 Bitmask）
- 為新的 prop PNG 建立 `<name>.tscn` 場景（自動套腳底錨點）
- 在對應的 `zone_<name>.tscn` 加上 `TileMapLayer_Ground` 節點

完成後你會在 Godot 左下角「檔案系統」看到新檔案。

---

## Step 2：打開 Godot 編輯器

1. 啟動 Godot 4.6
2. 第一次：「匯入」→ 選 `game/project.godot`
3. 左下角檔案系統 → 雙擊 `src/maps/zones/zone_<name>.tscn`（要編輯哪個 zone 開哪個）
4. 中央視窗顯示 2D 場景

---

## Step 3：塗 autotile 地形

1. 場景樹（左上）點選 `TileMapLayer_Ground` 節點
2. 視窗下方會出現 TileMap 面板 → 切到「**Terrains**」分頁
3. 選一個 Terrain（例：草地）→ 在 2D 視窗按住滑鼠**左鍵**塗
4. 切換成另一個 Terrain（例：柏油）繼續塗，邊緣 Godot 自動算融合
5. 想擦除 → 用 Eraser 工具或按 `Shift+左鍵`

> 多張 autotile？切換 TileMap 面板上方的 atlas 來源即可。

---

## Step 4：擺 prop

1. 左下檔案系統找到 `src/maps/props/<category>/<name>.tscn`
2. 拖到 2D 視窗想要的位置
3. **重要**：確認新增的 prop 在場景樹的 `YSortRoot` 底下（不是的話直接拖到 YSortRoot 裡）
4. 重複擺多個

> Y-sort 會自動處理遮擋順序 — 角色繞到樹後方會自動被擋；走到樹前方會擋住樹幹。不需要調 z-index。

---

## Step 5：存檔 + 測試

1. `Ctrl+S` 存檔
2. 按 `F6`（或右上角 ▶）「執行此場景」
3. 角色出現在 zone 中可走動：
   - 走到樹/桿後方時 prop 應正確擋住角色 → 沒有就是腳底錨點問題，回去 Step 4 看擺位
   - 撞不過樹幹底部、長椅本體 → 沒有的話 collision 設錯，可請程式組或 AI 重跑
   - 地形 Terrain 邊緣融合自然 → 破圖的話可能 bitmask 設錯，請 AI 重跑
4. 不滿意回 Step 3-4 調整，反覆迭代

---

## Step 6：提交

```bash
git add game/src/maps/ game/assets/textures/environment/
git commit -m "編輯 nccu 場景：地形 + prop 擺位"
git push
```

---

## Godot 操作速查（第一次用必看）

| 動作             | 操作                                         |
| ---------------- | -------------------------------------------- |
| 打開場景         | 雙擊 `.tscn` 檔                              |
| 在場景中加新節點 | 場景樹按 `+` 或 `Ctrl+A`                     |
| 移動節點         | 點選後拖拉，或按 `W` 進入移動模式            |
| 刪除節點         | 選中按 `Delete`                              |
| 場景樹拖移層級   | 直接拖（注意：prop 必須在 `YSortRoot` 底下） |
| 縮放視窗         | 滑鼠滾輪                                     |
| 平移視窗         | 中鍵拖、或空白鍵+左鍵拖                      |
| 存檔             | `Ctrl+S`                                     |
| 執行此場景       | `F6`                                         |
| 復原             | `Ctrl+Z`                                     |

### ⚠️ 避免做這些

- 不要動 `src/` 底下任何 `.gd` 程式檔
- 不要刪除 `YSortRoot`、`Player`、`Transitions` 節點
- 不要改 prop 的 `Sprite2D.offset`（已自動設）
- 不要刪除既有的 `.tres` 或 `PropTemplate.tscn`

如果不小心動到，按 `Ctrl+Z` 復原；存檔過了就用 `git checkout <檔案>` 還原。

---

## 提交前最終自檢

push 前再過一次：

- [ ] Godot 中執行該 zone 沒有錯誤訊息（控制台無紅字）
- [ ] 角色走到 prop 後方時，prop 正確擋住角色（Y-sort）
- [ ] 角色撞不過樹幹/桿底，但能繞到後面
- [ ] 地形 Terrain 邊緣融合自然，沒有破圖
- [ ] `git diff` 只動到 `assets/textures/environment/` 與 `src/maps/`，沒誤動其他檔案

---

## 遇到問題？

- **AI 跑完但 Godot 看不到新檔** → 在 Godot 中按 `Ctrl+Shift+R` 重新掃描檔案系統
- **Terrain 邊緣亂塗** → 進 `<zone>_terrain.tres` 檢查 Terrain Set 的 bitmask；不確定就請 AI 重跑 prompt
- **Prop 擺進去 Y-sort 錯亂** → 確認 prop 在 `YSortRoot` 底下，且 PNG 腳底錨點正確
- **任何不確定的事** → 在團隊頻道貼 screenshot 問程式組
