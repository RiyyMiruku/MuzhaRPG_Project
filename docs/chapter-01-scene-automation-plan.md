# 第一章場景自動化計畫

> **對象**：專案負責人 / 程式 / 場景設計。**用途**：第一章 7 個 zone 的場景搭建策略——以最小人工達成可用品質。
> **狀態**：規劃中（2026-05-14）。實作前需先跑最小驗證實驗（見 §7）。

---

## 1. 目標與範圍

讓第一章「鐵門後的那個人」的場景搭建工作量最小化。**美術已大致到位（NPC、props、tilesets 多數已生成），瓶頸從美術轉移到「場景擺位 + 對話 + 邏輯」**——本計畫處理前者：**用腳本 + LLM 推演自動產出 zone .tscn**，讓設計人只審截圖、不擺座標。

**不在範圍內**：對話 beat 編寫、信任值系統設計、quest 流程（屬於後續另一份計畫）。

---

## 2. 第一章 zone 清單

按 [story/chapters/chapter_01_arrival/draft.md](../story/chapters/chapter_01_arrival/draft.md) 推演，第一章至少需要 **7 個 zone**：

| Zone ID | 場景 | 時期 | 主要劇情用途 |
|---|---|---|---|
| `zone_pharmacy_modern` | 榮昌中藥行（現代，鎖門 / 灰塵 / 塗黑全家福） | 現代 | 開場、穿越觸發點、現代線蒐證 |
| `zone_pharmacy_1983` | 榮昌中藥行（1983 內部，營業狀態） | 1983 | 主要劇情舞台、配藥教學、與祖父互動 |
| `zone_market_1983` | 木柵市場（1983 街景、攤販林立） | 1983 | 跑腿送藥、認識阿桃姨、其他 NPC |
| `zone_market_modern` | 木柵市場（現代） | 現代 | 跟老周問話、現代線探查 |
| `zone_pharmacy_backyard` | 藥行後院 + 上鎖房間 | 1983 | 第一章結尾關鍵場景 |
| `zone_apartment_muzha` | 老公寓（阿謙住處 / 父親遺物） | 現代 | 現代線蒐證 |
| `zone_law_office` | 律師事務所 | 現代 | 繼承文件 / 「祖父林榮昌」名字揭露 |

部分 zone 可能共用底圖（市場 1983 / 現代用同一 tilemap + 不同 props 切換），實作時再決定。

---

## 3. 現況快照（2026-05-14）

| 項目 | 狀態 |
|---|---|
| 故事劇本 | ✅ [draft.md](../story/chapters/chapter_01_arrival/draft.md) 完整 71 行 |
| 結構化資產清單 | ✅ [assets.json](../story/chapters/chapter_01_arrival/assets.json) |
| NPC 角色（13 個） | ✅ 主角 `lin_siqian`（原 `player` folder，已改名以對齊 lore）+ 11 個 NPC 已生成；❌ 缺 `a_tao_yi` moving 變體 |
| Props（25 個 .tscn） | ✅ 全數備齊於 [game/src/maps/props/](../game/src/maps/props/) |
| Tileset autotile PNG | ✅ 3 張 in [game/assets/textures/tilesets/](../game/assets/textures/tilesets/)；❌ 尚未掛進 TileMapDual |
| 建築（6 棟）PNG | ✅ 已生成且 import；⚠️ **視角不對**（見 §4） |
| Zone .tscn | ⚠️ 僅 [zone_market.tscn](../game/src/maps/zones/zone_market.tscn) 骨架，ColorRect 背景 |
| Iso 測試場 | ✅ [zone_iso_test.tscn](../game/src/maps/zones/zone_iso_test.tscn) 含 TileMapDual + 3 套 iso autotile |

---

## 4. 建築視角不一致問題

6 棟建築（藥行 ×2、公寓、律師事務所、店屋 ×2）的 `asset.json` 標記 `"view": "high_top_down"`，但實際圖是**正面或半立面立繪**，跟 iso 街景擺一起會穿幫。

**根因**：當初走 Pixellab `/map-objects` 端點生成（卡通建築立繪），該端點**沒有 iso 參數**。經 2026-05-14 查 OpenAPI 確認：`/create-image-pixflux` 才有 `isometric: true` flag（"weakly guiding",需在 description 同時帶 "isometric view / 30-degree" 字眼才穩定）。

### 解法（2026-05-14 已落實）

`pipeline/orchestrators/prop.py` 新增 `--kind=iso_building`,呼叫新 wrapper `pixellab_client.submit_pixflux_image(isometric=True, ...)`。Dashboard Create modal 也加了對應選項。

**全 6 棟一律 iso（2026-05-14 已落實）**：

| 建築 | 狀態 |
|---|---|
| pharmacy_rongchang_1983 | ✅ iso_building 重生完成 |
| pharmacy_rongchang_modern | ✅ iso_building 重生完成（但「廢棄/封門」氛圍未充分,description 可再調 + remake） |
| market_shophouse_minnan | ✅ iso_building 重生完成 |
| market_shophouse_concrete | ✅ iso_building 重生完成 |
| law_office_muzha | ✅ iso_building 重生完成 |
| old_apartment_muzha | ✅ iso_building 重生完成 |

**仍需做的事**：律師事務所跟公寓劇情會切進室內 zone（zone_law_office / zone_apartment_muzha）—— zone transition 是 gameplay 邏輯,跟 iso 立體外觀並存,玩家在街景按互動鍵即觸發 fade 進室內。

---

## 5. 場景自動擺位策略（三層架構）

### Level 1：YAML layout → 腳本擺位（確定可行）

設計人或 LLM 寫 high-level layout，Python 腳本算座標 + 產 .tscn。

```yaml
# story/chapters/chapter_01_arrival/zones/pharmacy_1983.yaml
zone: zone_pharmacy_1983
size: [20, 15]              # 格數
tilemap:
  base: market_concrete_tile
props:
  - id: medicine_cabinet_new
    anchor: north_wall
    offset: [2, 0]
    count: 3
  - id: shop_counter_wood
    anchor: center
  - id: wooden_stool_old
    anchor: relative_to(shop_counter_wood)
    offset: [0, 2]
  - id: lantern_paper_red
    anchor: entrance
npcs:
  - id: lin_rongchang
    anchor: behind(shop_counter_wood)
```

- 腳本：`scripts/build_zone.py`
- 輸入：上述 YAML + [art_source/manifest.json](../art_source/manifest.json)（資產 footprint / collision 元資料）
- 輸出：`game/src/maps/zones/zone_<name>.tscn`
- 解析 `anchor` 語法 → 算 iso 座標 → emit `[node ... instance=ExtResource(...)]`

**人類成本**：寫 7 個 YAML（每個 ~30 行）+ 審截圖。

### Level 2：LLM 從劇本推演 layout（半自動）

我（Claude）讀 [draft.md](../story/chapters/chapter_01_arrival/draft.md) + [assets.json](../story/chapters/chapter_01_arrival/assets.json) **直接寫 Level 1 的 YAML**。例如：

劇本「藥櫃還在、櫃台還在、牆上的全家福還在」→ 推演：
- 藥櫃靠後牆 ×3（中藥行典型佈局）
- 櫃台横向擋中央
- 全家福掛櫃台後方牆
- 椅子在櫃台前（顧客等抓藥）

**人類成本**：審「擺得對不對」的語意層級回饋。例「藥櫃應該靠左牆不是後牆」→ 我改 YAML 重生。**設計人不碰座標**。

### Level 3：Vision loop（試驗性）

1. 腳本產 `.tscn`
2. `godot --headless --quit --script tools/snapshot.gd <zone>` → 截圖
3. Claude **看截圖**（多模態），檢查穿牆 / Y-sort / 視覺重心
4. 自動改 YAML 重生再截圖
5. 收斂後才呈現給設計人最終版

**前置條件**：Headless 截圖腳本（~30 行 GDScript），需先實作。

---

## 6. TileMapDual 整合策略

[TileMapDual](https://github.com/GilaPixel/TileMapDual) addon（[docs/tilemapdual-guide.md](tilemapdual-guide.md)）的地形塗法跟一般 TileMap 不同。**自動化的關鍵卡點是 `tile_map_data = PackedByteArray("...")` 二進位編碼**。

### 可靠度排序

| 路徑 | 描述 | 風險 | 自動化程度 |
|---|---|---|---|
| **A. Python 直接寫 PackedByteArray** | 逆向 12-byte-per-cell 編碼，直接吐 .tscn | 🔴 高 — 錯一 byte 整 zone 跑不出來 | 100% |
| **B. `@tool` GDScript 在編輯器內塗** | YAML → GDScript 用 `set_cell()` 程式化塗 | 🟢 低 — 用 Godot 自己 API | 90%（設計人按一次 Bake 按鈕） |
| **C. `godot --headless` 跑批次** | 同 B 邏輯但 CLI 化 | 🟡 中 — TileMapDual `_ready()` 在 headless 是否能正確初始化 Display 子節點未驗證 | 100% |

### 建議

**先走路徑 B**，理由：
- 編碼風險為零（用 Godot 公開 API）
- 設計人按一下 Bake 按鈕的成本，遠低於 debug PackedByteArray
- B 通了再花半天試 C（CLI 化），失敗回退 B

---

## 7. 最小驗證實驗（半天內可知行不行）

在投入大規模實作前，先做一個端到端最小可行原型：

### 階段 0：TileMapDual `@tool` 寫入測試（30 分鐘）

**目標**：驗證 GDScript 程式化塗 TileMapDual 是否能正確生成 tile_map_data。

1. 寫一個 dummy `@tool` 腳本（attach 到 zone root）
2. 在 `_ready()` 或 inspector 按鈕中跑 `set_cells_terrain_connect()` 塗死的 5 個座標
3. 設計人在 Godot 開該 zone，存檔
4. 檢查：(a) 5 格有正確刷出，(b) 邊界自動拼接，(c) 存檔後 .tscn 的 `tile_map_data` 不為空

**通過條件**：5 格 iso 地形正確顯示且自動邊界 → 可進階段 1。
**失敗處理**：debug 後再決定路徑 A（風險高但全自動）或退回手畫。

### 階段 1：單一 zone 端到端（半天）

**目標**：驗證「YAML → .tscn → 截圖」流程在一個 zone 完整跑通。

選 `zone_pharmacy_1983`（劇情核心 zone）試做：

1. Claude 寫 [pharmacy_1983.yaml](../story/chapters/chapter_01_arrival/zones/) 初稿（從 draft.md 推演）
2. 寫 `scripts/build_zone.py` 解析器（讀 YAML，產 .tscn 含 props + npcs，TileMapDual 部分先空著）
3. 寫 `tools/zone_baker.gd`（`@tool`，讀 YAML tilemap 段，程式塗 TileMapDual）
4. 寫 `tools/snapshot.gd`（headless 開 zone，截圖存 PNG）
5. 跑通後，設計人在 Godot 跑 zone，回饋 layout 對不對

**通過條件**：截圖看起來「合理」（不一定漂亮，但不穿牆、props 在合理位置、tilemap 有刷出）→ 可擴展。

### 階段 2：擴展到 7 個 zone（1–2 天）

通過階段 1 後：
1. Claude 一次寫完 7 個 zone 的 YAML 初稿
2. 批次跑 builder → 7 張截圖
3. 設計人審圖 → 回饋「藥行 1983 的藥櫃位置不對」
4. Claude 改 YAML 重生
5. 反覆 2–3 輪收斂

**人類總成本**：階段 2 約 4–6 小時（純審圖 + 語意回饋，不碰座標）。

---

## 8. 預期工時拆解

假設階段 0 驗證通過。

| 任務 | 執行者 | 估時 |
|---|---|---|
| 改 orchestrator 支援 iso building + 重生藥行外觀 | Claude | 1.5 小時 |
| 生成 `a_tao_yi` moving 變體 | Claude | 15 分鐘 |
| 寫 `scripts/build_zone.py` Level 1 引擎 | Claude | 2 小時 |
| 寫 `tools/zone_baker.gd` @tool | Claude | 1 小時 |
| 寫 `tools/snapshot.gd` headless 截圖 | Claude | 1 小時 |
| 7 個 zone 的 YAML 初稿 | Claude | 1 小時 |
| 設計人審圖 + 語意回饋 ×2–3 輪 | 設計人 | 4–6 小時 |
| Claude 依回饋改 YAML 重生 | Claude | 2 小時 |
| **總計（設計人實際手動時間）** | — | **約 1.5 天** |

對比手動搭建 7 個 zone 的傳統作法（每個 zone 至少半天）：**設計人時間從 ~3.5 天壓到 ~1.5 天**。

---

## 9. 風險與未解問題

| 風險 | 機率 | 影響 | 緩解 |
|---|---|---|---|
| TileMapDual `@tool` API 在程式塗時行為跟編輯器塗不一致 | 中 | 高 | 階段 0 先驗證；失敗轉路徑 A |
| Headless mode 下 TileMapDual `_ready()` 掛掉 | 中 | 中 | 退回路徑 B（編輯器內按 Bake） |
| LLM 推演的 layout 美感不足 | 高 | 低 | Vision loop 自動迭代 + 設計人最後 10% 微調 |
| Iso Y-sort 深度錯亂 | 中 | 中 | 截圖人工檢查；必要時 layout 加 `z_priority` 欄位 |
| 視覺風格不統一（重生 iso 建築跟舊 props 風格差異） | 低 | 中 | Pixellab 參數固定 + 跑一致性檢查 |
| 第一章資產清單[assets.json](../story/chapters/chapter_01_arrival/assets.json) 跟 manifest 不同步 | 低 | 中 | builder 啟動時跑 cross-check，缺資產立即報錯 |
| Autotile PNG 16-cell 順序錯亂（Pixellab 隨機性）→ terrain 邊界拼接破洞 | 低 | 中 | 短期人工檢查；之後可在 `verify_in_godot` 階段加 PIL validator 檢查 (2,1) alpha~100% / (0,3) alpha~0%。zone_iso_test 三張 PNG 已實證 Pixellab 對 `/create-isometric-tile` 端點是穩定的 |

---

## 10. 後續（不在本計畫範圍）

完成本計畫後，剩下的第一章工作項目：

1. 對話 beat 編寫（~8–10 段，[dialogue-architecture.md](dialogue-architecture.md)）
2. 信任值系統實作（autoload + NPC `trust_thresholds`）
3. 雙時空切換機制（古地圖 prop 觸發 zone transition）
4. 身份揭露邏輯（events.gd 條件分支）
5. quest 流程（key item 取得、上鎖房間解謎）
6. 通關之夜長對話編排
7. 第一章結尾 cutscene（舊身分證 + 阿嬤燒香日期對照）

---

## 11. 相關文件

| 文檔 | 連結 |
|---|---|
| 第一章劇本草稿 | [story/chapters/chapter_01_arrival/draft.md](../story/chapters/chapter_01_arrival/draft.md) |
| 第一章資產清單 | [story/chapters/chapter_01_arrival/assets.json](../story/chapters/chapter_01_arrival/assets.json) |
| TileMapDual 設定 | [docs/tilemapdual-guide.md](tilemapdual-guide.md) |
| 場景設計工作流（手動） | [docs/scene-design-workflow.md](scene-design-workflow.md) |
| Pipeline 架構 | [pipeline/README.md](../pipeline/README.md) |
| 章節開發指南 | [docs/chapter-development.md](chapter-development.md) |
