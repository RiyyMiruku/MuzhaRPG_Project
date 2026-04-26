# ③ AI Prompt 範本

把素材丟進專案資料夾後（[① 素材製作與歸檔](1-asset-creation.md)），用本文 prompt 讓 AI 自動補完 Godot 端的場景結構。完成後再進 Godot 編輯地圖（[② 場景製作流程](2-scene-design.md)）。

---

## 使用方式

1. 在專案根目錄打開 Claude Code（或其他能讀寫專案檔案的 AI 助手，例如 Cursor、GitHub Copilot Workspace）
2. 把下方 **「整段 prompt」** 區塊**整段複製貼上**送出
3. 等 AI 跑完（通常 1–3 分鐘）
4. 在 Godot 中按 `Ctrl+Shift+R` 重新掃描檔案系統，確認新檔案已出現
5. 接著回到 [② 場景製作流程](2-scene-design.md) 的 Step 2 繼續

---

## 整段 prompt（複製貼上即可）

```text
你是 MuzhaRPG 專案的 Godot 4.6 助手。我（美術 / 地圖設計人）剛丟了新素材進專案，請依下列規則自動補完 Godot 端的場景結構，讓我可以直接打開 Godot 編輯地圖。

## 必讀文件（先讀懂）
1. game/assets/textures/environment/1-asset-creation.md  — 美術素材規格
2. game/assets/textures/environment/2-scene-design.md     — 場景製作流程（我接下來會做的事）
3. game/src/maps/README.md                                — 程式端工作流程
4. game/src/maps/props/Prop.gd                            — Prop 基底類別（含 foot_anchor 機制）
5. game/src/maps/props/PropTemplate.tscn                  — Prop 範本場景

## 你的任務

### A. 掃描新素材
比對 git status 與既有檔案，找出：
- tilesets/<zone>/autotile_*.png 中還沒對應 .tres 的
- props/{nature|urban}/*.png 中還沒對應 .tscn 的

### B. 為每個新 autotile PNG 建立 TileSet
在 game/src/maps/tilesets/ 建立 <zone>_terrain.tres：
- Texture Region Size = 16×16
- 加入該 autotile PNG 為 atlas source
- 建立 1 個 Terrain Set（mode = Match Corners and Sides）
- 該 Terrain Set 內定義 2 個 Terrain：lower（基底）、upper（覆蓋層）
- 4 格 16×16 的 bitmask 依 Pixellab 4-tile autotile 標準對應：
    (0,0) = 全 lower
    (1,0) = lower + upper 邊
    (0,1) = upper + lower 邊
    (1,1) = 全 upper
  （若不確定，給出 Terrain peering bits 的明確設定值）

### C. 為每個新 prop PNG 建立 .tscn
在 game/src/maps/props/<category>/<name>.tscn：
- 繼承 PropTemplate.tscn
- Sprite2D.texture 指向該 PNG（offset 不要設，Prop.gd 會自動處理）
- StaticBody2D/CollisionShape2D：依 PNG 高度給合理矩形：
    高 ≤ 16 px（小物：花圃）→ has_collision = false（草叢類），其他給底部 16×8 矩形
    高 17–48 px（中物：椅、燈）→ 整體矩形
    高 > 48 px（高物：樹、桿）→ 只設「底部 16×16」矩形，讓角色可走過上半部
- collision_layer = 4
- has_collision、is_interactable 預設 true / false

### D. 在 zone scene 加 TileMapLayer（若尚未有）
檢查 game/src/maps/zones/zone_<zone>.tscn：
- 若沒有 TileMapLayer_Ground 節點，加進去（在 YSortRoot 之上、之外）
- tile_set 屬性掛上對應的 <zone>_terrain.tres
- 不要刪除既有的 ColorRect 佔位（讓我之後手動刪）

### E. 報告
列出你建立/修改了哪些檔案，每個檔案一行：
- 路徑 + 一句話描述
- 任何不確定要我決定的地方（如 collision 大小）

## 限制
- 只動 game/src/maps/ 與必要的 .tscn
- 不要動任何 .gd 程式碼
- 不要刪除既有的 prop / tile / 場景節點
- 完成後請我自己開 Godot 預覽
```

---

## 跑完後的注意事項

- **第一次執行** Terrain Set 的 bitmask 可能需要在 Godot 中開 `.tres` 檢查 Terrain 預覽。若邊緣融合不對，回頭請 AI 調整 bitmask 或 peering bits。
- **Collision 大小**：AI 會依 PNG 高度自動分級，若實際遊玩感覺不對（撞不到、或撞到空氣），開 `.tscn` 用編輯器調 CollisionShape2D 的範圍，或回頭請 AI 重跑某個 prop。
- **AI 回報的「不確定項」**：認真看 — 通常代表規格有歧義，需要你決定（例：某個 prop 該不該擋角色）。

---

## 進階：只跑某一部分

如果你只想處理某一類素材，把 prompt 中「你的任務」段落保留你需要的子任務即可。例如：

- 只想建 prop scene：保留 A、C、E，刪除 B、D
- 只想建 tileset：保留 A、B、D、E，刪除 C
