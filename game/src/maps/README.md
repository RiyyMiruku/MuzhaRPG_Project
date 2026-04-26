# Maps — 場景地圖系統

混合式架構：**地形用 autotile + TileMap**（Terrain Set 自動處理邊緣），**裝飾物用獨立 Prop 場景**（Y-sort + collision）。

> **協作流程入口（場景設計人請先看）**：[docs/SCENE_DESIGN_WORKFLOW.md](../../../docs/SCENE_DESIGN_WORKFLOW.md)
> 內含「美術一句話 → AI 跑腳本」的批次匯入流程，本 README 是技術參考。

## 目錄結構

```
game/
├── assets/textures/environment/
│   ├── 1-asset-creation.md      # 給生圖人：素材製作與歸檔
│   ├── 2-scene-design.md        # 給地圖設計人：在 Godot 中組場景
│   ├── 3-ai-prompt.md           # 給 AI：自動補 Godot 結構的 prompt
│   ├── tilesets/                # 源圖：autotile + 一般 tileset PNG
│   │   ├── nccu/                #   autotile_grass_asphalt.png …
│   │   ├── market/
│   │   ├── riverside/           #   autotile_water_concrete.png
│   │   └── zhinan/              #   autotile_dirt_stone.png, autotile_stone_path.png
│   └── props/                   # 源圖：獨立裝飾物 PNG（一物件一張）
│       ├── nature/              #   tree_*, bush_*, rock_* …
│       └── urban/                #   bench_*, lamp_*, lantern_* …
│
└── src/maps/
    ├── main_world.tscn          # 主世界容器
    ├── tilesets/                # TileSet .tres 資源
    │   ├── <zone>_terrain.tres  #   autotile + 地形（Terrain Set，16×16）
    │   └── <zone>_props.tres    #   （未來：手繪 atlas，若需要）
    ├── props/                   # 可重用的 Prop 場景
    │   ├── Prop.gd              #   基底類別（含腳底錨點、collision、互動）
    │   ├── PropTemplate.tscn    #   範本 — 新建 prop 從此繼承
    │   ├── nature/              #   tree_oak.tscn, bush_flower.tscn …
    │   └── urban/                #   bench_wood.tscn, lamp_street.tscn …
    └── zones/                   # 各場景實例
        ├── zone_nccu.tscn
        ├── zone_market.tscn
        ├── zone_riverside.tscn
        └── zone_zhinan.tscn
```

---

## 工作流程

### A. 新增地形（autotile）

**推薦路徑（腳本自動）**：

1. PNG 直接放 `assets/textures/environment/tilesets/<zone>/autotile_<lower>_<upper>.png`
2. 跑 `python scripts/scaffold_zone.py`（或請 AI 跑）
3. 腳本會建 `src/maps/tilesets/<zone>_terrain.tres` + 在 zone scene 加 `TileMapLayer_Ground` 節點並掛好 TileSet
4. 在 Godot 開 TileSet 編輯器設 Terrain Set + peering bits（這步無法腳本化，太脆弱）
5. TileMap 面板 Terrains 分頁刷地板

**手動路徑**（理解流程用）：

1. 建 `src/maps/tilesets/<zone>_terrain.tres`、Region Size = 16×16、加 atlas source
2. Terrain Sets → New Terrain Set → mode = Match Corners and Sides
3. 為 4 格分別設 bitmask
4. 在 zone scene 加 `TileMapLayer_Ground` 節點掛 .tres

### B. 新增 Prop（裝飾物）

**推薦路徑（批次匯入）** — 一次處理一批同類物件：

1. PNG 丟 `temp/<任意子資料夾>/<物件名>/tile1.png` ~ `tileN.png`
2. 跑 `python scripts/import_assets.py --init temp/`（或請 AI 跑）→ 產生 `temp/import.toml` 草稿
3. 編輯 manifest 標註每個物件的 category / has_collision / collision 範圍
4. 跑 `python scripts/import_assets.py temp/import.toml`
5. 腳本會：重命名 PNG、搬到 `assets/.../props/<category>/`、生成對應 `.tscn` 繼承 PropTemplate
6. 擺進 Zone 的 `YSortRoot` 底下

**單張手動路徑**（少量素材）：

1. PNG 丟 `assets/textures/environment/props/{nature|urban}/`
2. 開 [PropTemplate.tscn](props/PropTemplate.tscn)、Save As 到 `src/maps/props/<category>/<name>.tscn`
3. Sprite2D.texture 指該 PNG（`offset` 不用調，[Prop.gd](props/Prop.gd) `_ready()` 會自動處理）
4. CollisionShape2D 設碰撞範圍；無碰撞 Prop（草叢、花圃）改 `has_collision = false`
5. 互動類設 `is_interactable = true` + `interact_prompt`
6. 拖到 Zone 的 `YSortRoot`

---

## Zone 場景標準結構

```
ZoneNCCU (Node2D)
├── Ground (ColorRect)              # 背景色塊佔位 — 等地形畫好後手動刪
├── ZoneLabel (Label)               # 區域名稱顯示（debug 用）
├── TileMapLayer_Ground             # 地磚、草地（無碰撞）— 由 scaffold_zone.py 加入
│                                   #   tile_set 掛 src/maps/tilesets/<zone>_terrain.tres
├── YSortRoot (Node2D, y_sort)      # Y 排序層
│   ├── Player                      #   玩家（zone scene 內或由 ZoneManager 注入）
│   └── (Prop / NPC instances)      #   拖入的 prop .tscn 與 NPC
└── Transitions (Node2D)            # 換場 Area2D（zone 邊界傳送點）
```

**關鍵**：
- `TileMapLayer_Ground` 必須在 `YSortRoot` **之外**（地面不參與 Y-sort）
- 渲染順序由場景樹 sibling 順序決定：Ground → ZoneLabel → TileMapLayer_Ground → YSortRoot 內依 y 排序
- 若需要可碰撞的牆面/欄杆，目前作法是用 prop 場景（從 [props/urban/](props/urban/)），不再額外開 `TileMapLayer_Walls`

---

## 設計原則

- **地形用 autotile**：地面、河堤、道路 — 用 Pixellab 生成、Terrain 筆刷塗
- **手繪 tileset 只給「重複的牆/欄杆」**：若需要的話，仍用同 zone 資料夾、單獨 .tres
- **裝飾物用獨立場景**：樹、路燈、公告欄 — 尺寸不規則、Y-sort、可能互動
- **腳底錨點**：Prop 的 `position` 代表角色站立的位置，[Prop.gd](props/Prop.gd) 自動處理 Sprite2D offset
- **碰撞分層**：玩家=1、NPC=2、Prop/牆=4

---

## 相關文件

- **協作流程入口（場景設計人）**：[docs/SCENE_DESIGN_WORKFLOW.md](../../../docs/SCENE_DESIGN_WORKFLOW.md)
- 給生圖人 — 素材製作：[1-asset-creation.md](../../assets/textures/environment/1-asset-creation.md)
- 給地圖設計人 — 場景組合：[2-scene-design.md](../../assets/textures/environment/2-scene-design.md)
- 大量 prop 匯入腳本：[scripts/IMPORT_ASSETS_README.md](../../../scripts/IMPORT_ASSETS_README.md)
- AI prompt 範本（少用，當腳本不適用時）：[3-ai-prompt.md](../../assets/textures/environment/3-ai-prompt.md)
- 角色實裝流程：[art_source/characters/3-asset-usage.md](../../../art_source/characters/3-asset-usage.md)
- 章節制開發：[docs/chapter-development.md](../../../docs/chapter-development.md)
- Zone 換場機制：[ZoneManager.gd](../core/classes/ZoneManager.gd)
- Prop 基底：[Prop.gd](props/Prop.gd)
